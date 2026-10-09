from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CenterCoord(BaseModel):
    latitude: float
    longitude: float


class HailEventSummary(BaseModel):
    id: str
    event_date: str
    name: str
    short_name: str
    max_hail_inches: float
    report_count: int
    max_warning_hail_inches: float
    center: CenterCoord


class HailReportItem(BaseModel):
    id: str
    valid: str
    latitude: float
    longitude: float
    hail_inches: float
    qualifier: str
    city: str
    county: str
    source: str
    remark: str


class WarningItem(BaseModel):
    event_id: int
    hail_tag_inches: float
    wind_tag_mph: int
    issued: str
    expires: str
    tier: str  # "core" | "envelope"
    basis: str
    geometry: Dict[str, Any]


class SelectedEventDetail(HailEventSummary):
    reports: List[HailReportItem]
    warnings: List[WarningItem]


class HailEventsCatalogResponse(BaseModel):
    source: str = "NWS local storm reports and storm-based warnings, via Iowa Environmental Mesonet"
    events: List[HailEventSummary]
    selected: Optional[SelectedEventDetail] = None
