from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime


class JurisdictionSyncStatus(BaseModel):
    last_sync: str
    status: str
    row_count: int
    etag: Optional[str] = None
    drift_pct: Optional[float] = None


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="healthy | degraded | critical")
    engine_version: str
    environment: str
    uptime_seconds: float
    database: str = Field(..., description="connected | disconnected | uninitialized")
    redis: str = Field(..., description="connected | disconnected | simulated")
    jurisdictions_synced: int
    jurisdictions_stale: List[str] = []
    last_sync_summary: Dict[str, JurisdictionSyncStatus] = {}
