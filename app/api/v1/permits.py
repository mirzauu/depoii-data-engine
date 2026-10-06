from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import verify_api_key
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.tasks.permit_sync import run_permit_sync_task, SyncTaskResult, _SYNC_HISTORY
from app.extraction.config_loader import list_configured_cities
from app.core.logging import logger

router = APIRouter(prefix="/permits", tags=["Permits Engine"])

from app.science.pilot_seed import PILOT_SEEDED_PERMITS

# In-memory storage for active permits warehouse (seeded with Pilot baseline)
_PERMIT_WAREHOUSE: Dict[str, DepoiiNormalizedPermitSchema] = {
    p.id: p for p in PILOT_SEEDED_PERMITS
}


class PermitSearchResponse(BaseModel):
    total: int
    count: int
    offset: int
    limit: int
    total_valuation: float
    permits: List[DepoiiNormalizedPermitSchema]


class PermitStatsResponse(BaseModel):
    total_permits: int
    total_valuation_usd: float
    by_category: Dict[str, int]
    by_roof_system: Dict[str, int]
    by_jurisdiction: Dict[str, int]


class SyncResponse(BaseModel):
    jurisdiction: str
    source_system: str
    status: str
    records_fetched: int
    records_normalized: int
    duplicates_removed: int
    duration_seconds: float
    etag: Optional[str]
    drift_pct: Optional[float]
    error_message: Optional[str] = None


@router.post("/sync/{city_key}", response_model=SyncResponse, dependencies=[Depends(verify_api_key)])
async def trigger_permit_sync(city_key: str) -> SyncResponse:
    """
    Triggers an on-demand municipal permit sync for the given city key (e.g. 'dallas_tx').
    Requires 'X-Depoii-Key' security header.
    """
    configured = list_configured_cities()
    if city_key not in configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City '{city_key}' is not configured. Available: {configured}",
        )

    result = await run_permit_sync_task(city_key)

    # Upsert normalized permits into in-memory warehouse
    for permit in result.normalized_permits:
        _PERMIT_WAREHOUSE[permit.id] = permit

    return SyncResponse(
        jurisdiction=result.jurisdiction,
        source_system=result.source_system,
        status=result.status,
        records_fetched=result.records_fetched,
        records_normalized=result.records_normalized,
        duplicates_removed=result.duplicates_removed,
        duration_seconds=result.duration_seconds,
        etag=result.etag,
        drift_pct=result.drift_pct,
        error_message=result.error_message,
    )


@router.get("/search", response_model=PermitSearchResponse)
async def search_permits(
    jurisdiction: Optional[str] = Query(None, description="e.g. 'Dallas, TX'"),
    state: Optional[str] = Query(None, description="2-letter state code e.g. 'TX'"),
    contractor: Optional[str] = Query(None, description="Contractor name substring"),
    category: Optional[str] = Query(None, description="Permit category"),
    probable_roof_system: Optional[str] = Query(None, description="Roof system membrane"),
    min_valuation: Optional[float] = Query(None, description="Minimum USD valuation"),
    max_valuation: Optional[float] = Query(None, description="Maximum USD valuation"),
    is_hail_storm_window: Optional[bool] = Query(None, description="Filter post-hail window"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PermitSearchResponse:
    """
    Searches normalized commercial roofing permits across all ingested municipal feeds.
    Returns typed records matching the Depoii canonical schema.
    """
    all_records = list(_PERMIT_WAREHOUSE.values())

    filtered = []
    for p in all_records:
        if jurisdiction and jurisdiction.lower() not in p.jurisdiction.lower():
            continue
        if state and state.upper() != p.state.upper():
            continue
        if contractor and contractor.lower() not in p.contractor_name.lower():
            continue
        if category and category.lower() != p.category.lower():
            continue
        if probable_roof_system and probable_roof_system.lower() not in p.probable_roof_system.lower():
            continue
        if min_valuation is not None and p.valuation < min_valuation:
            continue
        if max_valuation is not None and p.valuation > max_valuation:
            continue
        if is_hail_storm_window is not None and p.is_hail_storm_window != is_hail_storm_window:
            continue
        filtered.append(p)

    # Sort descending by valuation
    filtered.sort(key=lambda x: x.valuation, reverse=True)

    paginated = filtered[offset: offset + limit]
    total_val = sum(p.valuation for p in filtered)

    return PermitSearchResponse(
        total=len(filtered),
        count=len(paginated),
        offset=offset,
        limit=limit,
        total_valuation=round(total_val, 2),
        permits=paginated,
    )


@router.get("/stats", response_model=PermitStatsResponse)
async def get_permit_stats() -> PermitStatsResponse:
    """
    Returns aggregate breakdown and total valuation across the permit warehouse.
    """
    all_records = list(_PERMIT_WAREHOUSE.values())

    by_cat: Dict[str, int] = {}
    by_sys: Dict[str, int] = {}
    by_jur: Dict[str, int] = {}
    total_val = 0.0

    for p in all_records:
        by_cat[p.category] = by_cat.get(p.category, 0) + 1
        by_sys[p.probable_roof_system] = by_sys.get(p.probable_roof_system, 0) + 1
        by_jur[p.jurisdiction] = by_jur.get(p.jurisdiction, 0) + 1
        total_val += p.valuation

    return PermitStatsResponse(
        total_permits=len(all_records),
        total_valuation_usd=round(total_val, 2),
        by_category=by_cat,
        by_roof_system=by_sys,
        by_jurisdiction=by_jur,
    )
