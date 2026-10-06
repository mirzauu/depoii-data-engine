from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Metrics definitions
PERMITS_INGESTED = Counter(
    "depoii_permits_ingested_total",
    "Total commercial building permits normalized and ingested",
    ["jurisdiction", "source"],
)

SCRAPER_DURATION = Histogram(
    "depoii_scraper_duration_seconds",
    "Duration of municipal scraper jobs in seconds",
    ["jurisdiction"],
    buckets=[1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

SCRAPER_FAILURES = Counter(
    "depoii_scraper_failures_total",
    "Total failed municipal scraper attempts",
    ["jurisdiction", "error_type"],
)

ACTIVE_STREAMING_JOBS = Gauge(
    "depoii_active_streaming_jobs",
    "Number of active SSE streaming scraper sessions",
)

SYNC_FRESHNESS_HOURS = Gauge(
    "depoii_sync_freshness_hours",
    "Hours elapsed since last successful municipal sync",
    ["jurisdiction"],
)


def get_metrics_data() -> tuple[bytes, str]:
    """
    Returns Prometheus metrics payload and content type.
    """
    return generate_latest(), CONTENT_TYPE_LATEST
