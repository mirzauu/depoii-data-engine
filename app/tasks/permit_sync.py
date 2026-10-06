import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from app.extraction.config_loader import load_city_config, CityConfig
from app.extraction.socrata_client import SocrataClient, SocrataFetchResult
from app.extraction.accela_scraper import UniversalAccelaScraper, AccelaScraperResult
from app.science.normalizer import batch_normalize_permits
from app.science.deduplicator import deduplicate_permits_in_memory
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.core.logging import logger
from app.observability.metrics import PERMITS_INGESTED, SCRAPER_DURATION, SCRAPER_FAILURES, SYNC_FRESHNESS_HOURS
from app.observability.alerting import send_ops_alert

DRIFT_WARNING_THRESHOLD = 0.50  # 50% change triggers drift warning


@dataclass
class SyncTaskResult:
    jurisdiction: str
    source_system: str
    status: str  # "SUCCESS" | "UNCHANGED" | "ZERO_ROWS_BLOCKED" | "DRIFT_WARNING" | "FAILED" | "SKIPPED"
    records_fetched: int
    records_normalized: int
    duplicates_removed: int
    duration_seconds: float
    etag: Optional[str]
    drift_pct: Optional[float]
    normalized_permits: List[DepoiiNormalizedPermitSchema]
    error_message: Optional[str] = None


# In-memory registry for tracking sync state across runs
_SYNC_HISTORY: Dict[str, Dict[str, Any]] = {}


async def run_permit_sync_task(
    city_key: str,
    client: Optional[SocrataClient] = None,
    mock_raw_data: Optional[List[Dict[str, Any]]] = None,
) -> SyncTaskResult:
    """
    Executes an end-to-end permit sync for a given jurisdiction (Socrata or Accela):
    1. ETag caching (304 Not Modified support for SODA feeds)
    2. Zero-row overwrite protection (blocks wiping database on scraper breakage)
    3. Row count drift detection (>50% difference raises warning)
    4. Canonical normalization
    5. Cross-source deduplication
    """
    start_time = time.time()
    config = load_city_config(city_key)

    # Check previous sync for ETag and row count baseline
    prev_sync = _SYNC_HISTORY.get(config.jurisdiction, {})
    prev_etag = prev_sync.get("etag")
    prev_count = prev_sync.get("row_count", 0)

    # ==========================================
    # BRANCH A: Socrata Open Data (Tier 1)
    # ==========================================
    if config.platform == "socrata":
        socrata_cfg = config.socrata
        if not socrata_cfg:
            return SyncTaskResult(
                jurisdiction=config.jurisdiction,
                source_system="socrata",
                status="FAILED",
                records_fetched=0,
                records_normalized=0,
                duplicates_removed=0,
                duration_seconds=round(time.time() - start_time, 2),
                etag=None,
                drift_pct=None,
                normalized_permits=[],
                error_message="Missing socrata configuration block",
            )

        if mock_raw_data is not None:
            raw_records = mock_raw_data
            fetch_result = SocrataFetchResult(
                domain=socrata_cfg.domain,
                dataset_id=socrata_cfg.dataset_id,
                is_modified=True,
                status_code=200,
                etag="W/\"mock-etag-01\"",
                records=raw_records,
                total_records=len(raw_records),
            )
        else:
            socrata_client = client or SocrataClient()
            fetch_result = await socrata_client.fetch_all_pages(
                domain=socrata_cfg.domain,
                dataset_id=socrata_cfg.dataset_id,
                etag=prev_etag,
                max_records=config.rate_limit.batch_size if config.rate_limit else 2000,
            )

        duration = round(time.time() - start_time, 2)

        # 304 Not Modified
        if not fetch_result.is_modified:
            logger.info(f"[SyncTask] Data unchanged for {config.jurisdiction} (ETag match)")
            return SyncTaskResult(
                jurisdiction=config.jurisdiction,
                source_system="socrata",
                status="UNCHANGED",
                records_fetched=0,
                records_normalized=prev_sync.get("records_normalized", 0),
                duplicates_removed=0,
                duration_seconds=duration,
                etag=prev_etag,
                drift_pct=0.0,
                normalized_permits=[],
            )

        if fetch_result.error:
            logger.error(f"[SyncTask] Error fetching {config.jurisdiction}: {fetch_result.error}")
            return SyncTaskResult(
                jurisdiction=config.jurisdiction,
                source_system="socrata",
                status="FAILED",
                records_fetched=0,
                records_normalized=0,
                duplicates_removed=0,
                duration_seconds=duration,
                etag=None,
                drift_pct=None,
                normalized_permits=[],
                error_message=fetch_result.error,
            )

        current_count = fetch_result.total_records
        raw_records = fetch_result.records
        current_etag = fetch_result.etag

    # ==========================================
    # BRANCH B: Accela Citizen Access (Tier 2)
    # ==========================================
    elif config.platform == "accela":
        if mock_raw_data is not None:
            raw_records = mock_raw_data
            current_count = len(raw_records)
            current_etag = None
        else:
            scraper = UniversalAccelaScraper(city_key, config=config)
            accela_res = await scraper.scrape_permits()
            if accela_res.status == "FAILED":
                return SyncTaskResult(
                    jurisdiction=config.jurisdiction,
                    source_system="accela",
                    status="FAILED",
                    records_fetched=0,
                    records_normalized=0,
                    duplicates_removed=0,
                    duration_seconds=round(time.time() - start_time, 2),
                    etag=None,
                    drift_pct=None,
                    normalized_permits=[],
                    error_message=accela_res.error,
                )
            raw_records = accela_res.records
            current_count = accela_res.total_records
            current_etag = None

        duration = round(time.time() - start_time, 2)

    else:
        return SyncTaskResult(
            jurisdiction=config.jurisdiction,
            source_system=config.platform,
            status="SKIPPED",
            records_fetched=0,
            records_normalized=0,
            duplicates_removed=0,
            duration_seconds=round(time.time() - start_time, 2),
            etag=None,
            drift_pct=None,
            normalized_permits=[],
            error_message=f"Platform '{config.platform}' not supported",
        )

    # ==========================================
    # COMMON: Quality Gates & Normalization
    # ==========================================

    # 1. Guard against silent scraper failures (Zero-row block)
    if current_count == 0 and prev_count > 0:
        logger.critical(
            f"[SyncTask] ZERO_ROWS_BLOCKED for {config.jurisdiction}! "
            f"Expected ~{prev_count} records. Refusing to overwrite production data."
        )
        await send_ops_alert(
            f"Zero records returned for {config.jurisdiction} (expected ~{prev_count}). Ingestion blocked.",
            severity="critical",
            context={"jurisdiction": config.jurisdiction, "expected_baseline": prev_count},
        )
        SCRAPER_FAILURES.labels(jurisdiction=config.jurisdiction, error_type="ZERO_ROWS").inc()

        return SyncTaskResult(
            jurisdiction=config.jurisdiction,
            source_system=config.platform,
            status="ZERO_ROWS_BLOCKED",
            records_fetched=0,
            records_normalized=0,
            duplicates_removed=0,
            duration_seconds=duration,
            etag=current_etag,
            drift_pct=-1.0,
            normalized_permits=[],
            error_message="Zero records returned while previous run had data. Ingestion blocked.",
        )

    # 2. Drift calculation
    drift_pct = None
    status = "SUCCESS"
    if prev_count > 0:
        drift_pct = round((current_count - prev_count) / prev_count, 3)
        if abs(drift_pct) >= DRIFT_WARNING_THRESHOLD:
            status = "DRIFT_WARNING"
            logger.warning(
                f"[SyncTask] DRIFT_WARNING for {config.jurisdiction}: "
                f"Row count changed from {prev_count} to {current_count} ({drift_pct:+.1%})"
            )
            await send_ops_alert(
                f"Row count drifted {drift_pct:+.1%} for {config.jurisdiction} (from {prev_count} to {current_count})",
                severity="warning",
                context={"jurisdiction": config.jurisdiction, "drift_pct": drift_pct, "current": current_count},
            )

    # 3. Normalization (dispatches based on config.platform)
    batch_res = batch_normalize_permits(
        raw_records=raw_records,
        source="accela" if config.platform == "accela" else "socrata",
        jurisdiction=config.jurisdiction,
        state=config.state,
    )

    # 4. Cross-source Deduplication
    deduped_permits, dup_count = deduplicate_permits_in_memory(batch_res.records)

    # 5. Update in-memory sync history
    _SYNC_HISTORY[config.jurisdiction] = {
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "row_count": len(deduped_permits),
        "etag": current_etag,
        "records_normalized": len(deduped_permits),
        "drift_pct": drift_pct,
    }

    # 6. Prometheus Metrics Recording
    PERMITS_INGESTED.labels(jurisdiction=config.jurisdiction, source=config.platform).inc(len(deduped_permits))
    SCRAPER_DURATION.labels(jurisdiction=config.jurisdiction).observe(duration)
    SYNC_FRESHNESS_HOURS.labels(jurisdiction=config.jurisdiction).set(0.0)

    return SyncTaskResult(
        jurisdiction=config.jurisdiction,
        source_system=config.platform,
        status=status,
        records_fetched=current_count,
        records_normalized=len(deduped_permits),
        duplicates_removed=dup_count,
        duration_seconds=duration,
        etag=current_etag,
        drift_pct=drift_pct,
        normalized_permits=deduped_permits,
    )
