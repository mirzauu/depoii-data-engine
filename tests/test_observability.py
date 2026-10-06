import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.observability.alerting import send_ops_alert
from app.observability.metrics import get_metrics_data, PERMITS_INGESTED
from app.tasks.permit_sync import run_permit_sync_task


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        text = res.text
        assert "depoii_permits_ingested_total" in text
        assert "depoii_scraper_duration_seconds" in text
        assert "depoii_scraper_failures_total" in text


@pytest.mark.asyncio
async def test_ops_alert_logging():
    # Test warning dispatch
    warn_ok = await send_ops_alert(
        "Drift detected in Dallas feed: +52% volume",
        severity="warning",
        context={"jurisdiction": "Dallas, TX", "drift": 0.52},
    )
    assert warn_ok is True

    # Test critical dispatch
    crit_ok = await send_ops_alert(
        "Zero rows returned from Fort Worth portal! Ingestion blocked.",
        severity="critical",
        context={"jurisdiction": "Fort Worth, TX", "expected": 88},
    )
    assert crit_ok is True


@pytest.mark.asyncio
async def test_sync_task_observability_pipeline():
    mock_records = [
        {
            "permit_number": "METRIC-TEST-001",
            "issued_date": "2024-06-01",
            "street_address": "100 METRICS WAY",
            "contractor_name": "KPOST COMPANY",
            "estimated_cost": "500000",
            "work_description": "TPO roofing scope",
            "status": "Issued",
        }
    ]

    res = await run_permit_sync_task("dallas_tx", mock_raw_data=mock_records)
    assert res.status in ("SUCCESS", "DRIFT_WARNING")

    # Verify Prometheus metrics contain the updated counter
    data, _ = get_metrics_data()
    metrics_str = data.decode("utf-8")
    assert "depoii_permits_ingested_total" in metrics_str
