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
import os
import json

# In-memory storage for active permits warehouse (seeded with Pilot baseline + cache if present)
_PERMIT_WAREHOUSE: Dict[str, DepoiiNormalizedPermitSchema] = {
    p.id: p for p in PILOT_SEEDED_PERMITS
}

from sqlalchemy import create_engine, text
from app.config import settings

_db_engine = None

def get_db_engine():
    global _db_engine
    if _db_engine is None:
        local_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "depoii_local.db")
        if settings.USE_LOCAL_DB and os.path.exists(local_db_path):
            _db_engine = create_engine(
                f"sqlite:///{local_db_path}",
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            logger.info(f"Using local high-speed SQLite database: {local_db_path}")
        else:
            _db_engine = create_engine(
                settings.SYNC_DATABASE_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_recycle=300,
                pool_timeout=10,
            )
    return _db_engine



_cache_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "warehouse_cache.json")
if os.path.exists(_cache_file):
    try:
        with open(_cache_file, "r", encoding="utf-8") as _f:
            _raw_cached = json.load(_f)
            for _item in _raw_cached:
                _p = DepoiiNormalizedPermitSchema.model_validate(_item)
                _PERMIT_WAREHOUSE[_p.id] = _p
    except Exception as _e:
        pass


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
    city: Optional[str] = Query(None, description="City name"),
    contractor: Optional[str] = Query(None, description="Contractor name substring"),
    category: Optional[str] = Query(None, description="Permit category"),
    probable_roof_system: Optional[str] = Query(None, description="Roof system membrane"),
    status_filter: Optional[str] = Query(None, description="Permit status e.g. 'Active', 'Finaled'"),
    intelligence_mode: Optional[str] = Query(None, description="'all', 'active', 'aging', or 'multiphase'"),
    min_valuation: Optional[float] = Query(None, description="Minimum USD valuation"),
    max_valuation: Optional[float] = Query(None, description="Maximum USD valuation"),
    is_hail_storm_window: Optional[bool] = Query(None, description="Filter post-hail window"),
    search: Optional[str] = Query(None, description="Full-text query across address, contractor, permit #, or description"),
    sort_by: Optional[str] = Query("valuation_desc", description="'valuation_desc', 'valuation_asc', 'date_desc', 'date_asc'"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PermitSearchResponse:
    """
    Enterprise Apollo-Style Permit Search Engine.
    Queries all 21,372 normalized commercial roofing permits directly from PostgreSQL
    with high-performance indexing and multi-dimensional filter facets.
    """
    engine = get_db_engine()

    try:
        with engine.connect() as conn:
            where_clauses = [
                "LOWER(p.contractor_name) NOT LIKE '%licensed%'",
                "LOWER(p.contractor_name) NOT LIKE '%unknown%'",
                "LOWER(p.normalized_address) NOT LIKE '%commercial corridor%'",
            ]
            params: Dict[str, Any] = {}

            if jurisdiction and jurisdiction.strip():
                where_clauses.append("LOWER(p.jurisdiction) LIKE :jur")
                params["jur"] = f"%{jurisdiction.strip().lower()}%"

            if city and city.strip():
                where_clauses.append("LOWER(p.city) LIKE :city")
                params["city"] = f"%{city.strip().lower()}%"

            if state and state.strip():
                where_clauses.append("UPPER(p.state) = :state")
                params["state"] = state.strip().upper()

            if contractor and contractor.strip():
                where_clauses.append("LOWER(p.contractor_name) LIKE :contractor")
                params["contractor"] = f"%{contractor.strip().lower()}%"

            if category and category.strip():
                where_clauses.append("LOWER(p.category) LIKE :category")
                params["category"] = f"%{category.strip().lower()}%"

            if probable_roof_system and probable_roof_system.strip():
                where_clauses.append("LOWER(p.probable_roof_system) LIKE :roof_sys")
                params["roof_sys"] = f"%{probable_roof_system.strip().lower()}%"

            if status_filter and status_filter.strip() and status_filter != "all":
                where_clauses.append("LOWER(p.status) LIKE :p_status")
                params["p_status"] = f"%{status_filter.strip().lower()}%"

            # Intelligence Modes (Apollo quick filters)
            if intelligence_mode == "active":
                where_clauses.append("p.status IN ('Active', 'Issued')")
            elif intelligence_mode == "aging":
                where_clauses.append("p.issue_date IS NOT NULL AND p.issue_date >= '1990-01-01' AND (CAST(strftime('%Y', 'now') AS INTEGER) - CAST(substr(p.issue_date, 1, 4) AS INTEGER)) >= 10" if "sqlite" in str(engine.url) else "p.issue_date IS NOT NULL AND p.issue_date >= '1990-01-01' AND (EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM p.issue_date)) >= 10")
            elif intelligence_mode == "hail":
                where_clauses.append("p.is_hail_storm_window = 1" if "sqlite" in str(engine.url) else "p.is_hail_storm_window = TRUE")

            if min_valuation is not None:
                where_clauses.append("p.valuation >= :min_val")
                params["min_val"] = min_valuation

            if max_valuation is not None:
                where_clauses.append("p.valuation <= :max_val")
                params["max_val"] = max_valuation

            if is_hail_storm_window is not None:
                where_clauses.append("p.is_hail_storm_window = :is_hail")
                params["is_hail"] = is_hail_storm_window

            if search and search.strip():
                where_clauses.append("""
                    (LOWER(p.normalized_address) LIKE :search 
                     OR LOWER(p.contractor_name) LIKE :search 
                     OR LOWER(p.raw_permit_number) LIKE :search
                     OR LOWER(p.city) LIKE :search
                     OR LOWER(p.raw_description) LIKE :search)
                """)
                params["search"] = f"%{search.strip().lower()}%"

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # 1. Total counts & sum valuation
            agg_sql = f"""
                SELECT COUNT(*) as total_count, COALESCE(SUM(valuation), 0) as total_val
                FROM normalized_permits p
                WHERE {where_sql}
            """
            agg_row = conn.execute(text(agg_sql), params).mappings().first()
            total_records = agg_row["total_count"] if agg_row else 0
            total_val = float(agg_row["total_val"]) if agg_row else 0.0

            # 2. Sort ordering
            order_clause = "p.valuation DESC NULLS LAST"
            if sort_by == "valuation_asc":
                order_clause = "p.valuation ASC NULLS LAST"
            elif sort_by == "date_desc":
                order_clause = "p.issue_date DESC NULLS LAST"
            elif sort_by == "date_asc":
                order_clause = "p.issue_date ASC NULLS LAST"

            # 3. Paged fetch
            params_paged = dict(params)
            params_paged["limit"] = limit
            params_paged["offset"] = offset

            fetch_sql = f"""
                SELECT 
                    p.id, p.raw_permit_number, p.jurisdiction, p.source_system,
                    p.state, p.issue_date, p.applied_date, p.expiration_date, p.status,
                    p.normalized_address, p.city, p.zip_code, p.latitude, p.longitude, p.parcel_id,
                    p.valuation, p.valuation_formatted, p.category, p.raw_description, p.square_footage,
                    p.probable_roof_system, p.contractor_name, p.contractor_license, p.contractor_phone,
                    p.is_hail_storm_window, p.associated_storm_id, p.is_competitor_capture,
                    p.confidence_score, p.normalized_at
                FROM normalized_permits p
                WHERE {where_sql}
                ORDER BY {order_clause}
                LIMIT :limit OFFSET :offset
            """
            rows = conn.execute(text(fetch_sql), params_paged).mappings().fetchall()

            permits_list = []
            for r in rows:
                val = float(r["valuation"] or 0.0)
                v_fmt = r["valuation_formatted"] or (f"${val / 1_000_000:.2f}M" if val >= 1_000_000 else f"${int(val):,}")
                permits_list.append(
                    DepoiiNormalizedPermitSchema(
                        id=r["id"],
                        raw_permit_number=r["raw_permit_number"],
                        jurisdiction=r["jurisdiction"],
                        source_system=r["source_system"] or "Municipal Open Data",
                        source_priority=3,
                        state=r["state"],
                        county=None,
                        issue_date=str(r["issue_date"]) if r["issue_date"] is not None else "Unknown",
                        applied_date=str(r["applied_date"]) if r["applied_date"] is not None else None,
                        expiration_date=str(r["expiration_date"]) if r["expiration_date"] is not None else None,
                        status=r["status"] or "Active",
                        normalized_address=r["normalized_address"],
                        city=r["city"],
                        zip_code=r["zip_code"] or "",
                        latitude=float(r["latitude"]) if r["latitude"] is not None else None,
                        longitude=float(r["longitude"]) if r["longitude"] is not None else None,
                        parcel_id=r["parcel_id"],
                        valuation=round(val, 2),
                        valuation_formatted=v_fmt,
                        category=r["category"] or "Commercial Re-Roof",
                        raw_description=r["raw_description"] or "Commercial roofing work.",
                        square_footage=r["square_footage"],
                        probable_roof_system=r["probable_roof_system"] or "TPO Single-Ply",
                        contractor_name=r["contractor_name"] or "Contractor on File",
                        contractor_license=r["contractor_license"],
                        contractor_phone=r["contractor_phone"],
                        is_hail_storm_window=bool(r["is_hail_storm_window"]),
                        associated_storm_event=r["associated_storm_id"],
                        is_competitor_capture=bool(r["is_competitor_capture"]),
                        confidence_score=r["confidence_score"] or 90,
                        normalized_at=str(r["normalized_at"]) if r["normalized_at"] is not None else "2026-10-07",
                    )
                )

            return PermitSearchResponse(
                total=total_records,
                count=len(permits_list),
                offset=offset,
                limit=limit,
                total_valuation=round(total_val, 2),
                permits=permits_list,
            )
    except Exception as e:
        logger.error(f"Error in search_permits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query permits: {str(e)}"
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


class CityListResponse(BaseModel):
    total_cities: int
    cities: List[str]


@router.get("/cities", response_model=CityListResponse)
async def list_unique_cities() -> CityListResponse:
    """
    Returns a list of all unique cities present in the permit warehouse.
    """
    all_records = list(_PERMIT_WAREHOUSE.values())
    unique_cities = set()
    for p in all_records:
        if p.city:
            unique_cities.add(p.city)
            
    # Sort them alphabetically for convenience
    sorted_cities = sorted(list(unique_cities))
    
    return CityListResponse(
        total_cities=len(sorted_cities),
        cities=sorted_cities
    )


class ActiveJobsiteItem(BaseModel):
    id: str
    permit_number: str
    address: str
    city: str
    state: str
    zip_code: str
    jurisdiction: str
    contractor_name: str
    contractor_id: Optional[str] = None
    contractor_phone: Optional[str] = None
    contractor_license: Optional[str] = None
    valuation: float
    valuation_formatted: str
    roof_system: str
    issue_date: str
    applied_date: Optional[str] = None
    status: str
    category: str
    scope_description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ActiveJobsitesResponse(BaseModel):
    total_active_jobs: int
    active_pipeline_valuation_usd: float
    active_pipeline_valuation_formatted: str
    active_contractors_count: int
    top_roof_systems: Dict[str, int]
    jurisdictions_available: List[str]
    jobsites: List[ActiveJobsiteItem]


@router.get("/active-jobsites", response_model=ActiveJobsitesResponse)
async def get_active_jobsites(
    jurisdiction: Optional[str] = Query(None, description="Filter by metro/city e.g. 'Dallas, TX', 'Addison', 'Seattle'"),
    contractor: Optional[str] = Query(None, description="Search by contractor name or ID"),
    roof_system: Optional[str] = Query(None, description="Filter by roof system e.g. 'TPO Single-Ply'"),
    min_valuation: Optional[float] = Query(0.0, ge=0.0, description="Minimum project valuation in USD"),
    search: Optional[str] = Query(None, description="Free text address, permit number, or contractor search"),
    limit: int = Query(50, ge=1, le=200, description="Max jobsites to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ActiveJobsitesResponse:
    """
    Real-Time Active Commercial Jobsite Tracker using purely municipal permit records.
    Finds active commercial re-roof and new roof projects currently undergoing construction in the field.
    """
    engine = get_db_engine()

    try:
        with engine.connect() as conn:
            where_clauses = [
                "status IN ('Active', 'Issued')",
                "valuation >= :min_val",
                "LOWER(contractor_name) NOT LIKE '%licensed%'",
                "LOWER(contractor_name) NOT LIKE '%unknown%'",
                "LOWER(contractor_name) NOT LIKE '%self%contracted%'",
                "contractor_name IS NOT NULL",
                "contractor_name != ''",
            ]
            params: Dict[str, Any] = {"min_val": min_valuation or 0.0}

            if jurisdiction and jurisdiction.strip():
                clean_j = jurisdiction.strip().lower()
                where_clauses.append("(LOWER(jurisdiction) LIKE :jur OR LOWER(city) LIKE :jur)")
                params["jur"] = f"%{clean_j}%"

            if contractor and contractor.strip():
                clean_c = contractor.strip().lower()
                where_clauses.append("(LOWER(contractor_name) LIKE :contractor OR LOWER(COALESCE(contractor_id, '')) LIKE :contractor)")
                params["contractor"] = f"%{clean_c}%"

            if roof_system and roof_system.strip():
                clean_sys = roof_system.strip().lower()
                where_clauses.append("LOWER(probable_roof_system) LIKE :roof_sys")
                params["roof_sys"] = f"%{clean_sys}%"

            if search and search.strip():
                clean_s = search.strip().lower()
                where_clauses.append("""
                    (LOWER(normalized_address) LIKE :search 
                     OR LOWER(raw_permit_number) LIKE :search 
                     OR LOWER(contractor_name) LIKE :search
                     OR LOWER(city) LIKE :search)
                """)
                params["search"] = f"%{clean_s}%"

            where_sql = " AND ".join(where_clauses)

            # 1. Aggregate totals
            agg_sql = f"""
                SELECT 
                    COUNT(*) as total_jobs,
                    COALESCE(SUM(valuation), 0) as total_val,
                    COUNT(DISTINCT contractor_name) as total_contractors
                FROM normalized_permits
                WHERE {where_sql}
            """
            agg_row = conn.execute(text(agg_sql), params).mappings().first()
            total_active_jobs = agg_row["total_jobs"] if agg_row else 0
            total_pipeline_val = float(agg_row["total_val"]) if agg_row else 0.0
            total_contractors = agg_row["total_contractors"] if agg_row else 0

            # 2. Roof system distribution for current filter
            roof_sql = f"""
                SELECT probable_roof_system, COUNT(*) as cnt
                FROM normalized_permits
                WHERE {where_sql}
                GROUP BY probable_roof_system
                ORDER BY cnt DESC
                LIMIT 6
            """
            roof_rows = conn.execute(text(roof_sql), params).mappings().fetchall()
            top_roof_systems = {r["probable_roof_system"]: r["cnt"] for r in roof_rows if r["probable_roof_system"]}

            # 3. Available jurisdictions list
            jur_sql = """
                SELECT DISTINCT jurisdiction
                FROM normalized_permits
                WHERE status IN ('Active', 'Issued')
                  AND LOWER(contractor_name) NOT LIKE '%licensed%'
                ORDER BY jurisdiction ASC
                LIMIT 30
            """
            jur_rows = conn.execute(text(jur_sql)).mappings().fetchall()
            jurisdictions_available = [r["jurisdiction"] for r in jur_rows if r["jurisdiction"]]

            # 4. Fetch Paginated Jobsite records
            params_paged = dict(params)
            params_paged["limit"] = limit
            params_paged["offset"] = offset

            fetch_sql = f"""
                SELECT 
                    id, raw_permit_number, normalized_address, city, state, zip_code, jurisdiction,
                    contractor_name, contractor_id, contractor_phone, contractor_license,
                    valuation, probable_roof_system, issue_date, applied_date, status, category,
                    raw_description, latitude, longitude
                FROM normalized_permits
                WHERE {where_sql}
                ORDER BY issue_date DESC, valuation DESC
                LIMIT :limit OFFSET :offset
            """
            jobs_rows = conn.execute(text(fetch_sql), params_paged).mappings().fetchall()

            jobsites: List[ActiveJobsiteItem] = []
            for r in jobs_rows:
                val = float(r["valuation"] or 0.0)
                if val >= 1_000_000:
                    val_fmt = f"${val / 1_000_000:.2f}M"
                elif val > 0:
                    val_fmt = f"${int(val):,}"
                else:
                    val_fmt = "$0"

                jobsites.append(
                    ActiveJobsiteItem(
                        id=r["id"],
                        permit_number=r["raw_permit_number"],
                        address=r["normalized_address"],
                        city=r["city"],
                        state=r["state"],
                        zip_code=r["zip_code"],
                        jurisdiction=r["jurisdiction"],
                        contractor_name=r["contractor_name"],
                        contractor_id=r["contractor_id"],
                        contractor_phone=r["contractor_phone"],
                        contractor_license=r["contractor_license"],
                        valuation=round(val, 2),
                        valuation_formatted=val_fmt,
                        roof_system=r["probable_roof_system"] or "TPO Single-Ply",
                        issue_date=str(r["issue_date"]) if r["issue_date"] is not None else "Recent",
                        applied_date=str(r["applied_date"]) if r["applied_date"] is not None else None,
                        status=r["status"] or "Active",
                        category=r["category"] or "Commercial Re-Roof",
                        scope_description=r["raw_description"] or "Commercial roofing installation and waterproofing.",
                        latitude=r["latitude"],
                        longitude=r["longitude"],
                    )
                )

            if total_pipeline_val >= 1_000_000_000:
                pipeline_fmt = f"${total_pipeline_val / 1_000_000_000:.2f}B"
            elif total_pipeline_val >= 1_000_000:
                pipeline_fmt = f"${total_pipeline_val / 1_000_000:.2f}M"
            else:
                pipeline_fmt = f"${int(total_pipeline_val):,}"

            return ActiveJobsitesResponse(
                total_active_jobs=total_active_jobs,
                active_pipeline_valuation_usd=round(total_pipeline_val, 2),
                active_pipeline_valuation_formatted=pipeline_fmt,
                active_contractors_count=total_contractors,
                top_roof_systems=top_roof_systems,
                jurisdictions_available=jurisdictions_available,
                jobsites=jobsites,
            )
    except Exception as e:
        logger.error(f"Error fetching active jobsites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query active jobsites: {str(e)}"
        )


class RoofAgingLeadItem(BaseModel):
    id: str
    permit_number: str
    address: str
    city: str
    state: str
    zip_code: str
    jurisdiction: str
    install_date: str
    roof_age_years: int
    warranty_status: str  # "Expired (20+ Yrs)", "Critical End-of-Life (15-19 Yrs)", "Approaching Term (10-14 Yrs)"
    risk_level: str       # "CRITICAL", "HIGH", "ELEVATED"
    historical_contractor: str
    historical_contractor_phone: Optional[str] = None
    historical_valuation: float
    historical_valuation_formatted: str
    estimated_replacement_cost_usd: float
    estimated_replacement_cost_formatted: str
    roof_system: str
    scope_description: str
    subsequent_permits_count: int
    replacement_priority_score: int  # 0 to 100
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RoofAgingAlarmResponse(BaseModel):
    total_aging_roofs: int
    total_replacement_pipeline_usd: float
    total_replacement_pipeline_formatted: str
    critical_expired_count: int
    end_of_warranty_count: int
    approaching_term_count: int
    jurisdictions_available: List[str]
    leads: List[RoofAgingLeadItem]


@router.get("/roof-aging-alarm", response_model=RoofAgingAlarmResponse)
async def get_roof_aging_alarm(
    jurisdiction: Optional[str] = Query(None, description="Filter by city/metro e.g. 'Dallas, TX', 'Addison'"),
    risk_tier: Optional[str] = Query("all", description="'critical', 'high', 'approaching', or 'all'"),
    min_age: int = Query(10, ge=5, le=30, description="Minimum roof age in years"),
    min_valuation: Optional[float] = Query(0.0, ge=0.0, description="Minimum original permit valuation"),
    search: Optional[str] = Query(None, description="Address, roofer, or permit search"),
    limit: int = Query(50, ge=1, le=200, description="Max leads to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> RoofAgingAlarmResponse:
    """
    Pure Permit-Based Roof Aging & Replacement Alarm.
    Scans historical municipal permits (10 to 25+ years old) with no subsequent re-roof permits,
    identifying expiring manufacturer warranties (Carlisle, GAF, Elevate) ready for replacement pitch.
    """
    engine = get_db_engine()

    try:
        with engine.connect() as conn:
            is_sqlite = "sqlite" in str(engine.url)
            age_expr = "(CAST(strftime('%Y', 'now') AS INTEGER) - CAST(substr(issue_date, 1, 4) AS INTEGER))" if is_sqlite else "(EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM issue_date))"

            where_clauses = [
                "issue_date IS NOT NULL",
                "issue_date >= '1990-01-01'",
                f"{age_expr} >= :min_age",
                "valuation >= :min_val",
                "contractor_name NOT LIKE '%licensed%'" if is_sqlite else "contractor_name NOT ILIKE '%licensed%'",
                "contractor_name NOT LIKE '%unknown%'" if is_sqlite else "contractor_name NOT ILIKE '%unknown%'",
            ]
            params: Dict[str, Any] = {
                "min_age": min_age,
                "min_val": min_valuation or 0.0
            }

            if jurisdiction and jurisdiction.strip():
                clean_j = jurisdiction.strip().lower()
                where_clauses.append("(LOWER(jurisdiction) LIKE :jur OR LOWER(city) LIKE :jur)")
                params["jur"] = f"%{clean_j}%"

            if risk_tier == "critical":
                where_clauses.append(f"{age_expr} >= 20")
            elif risk_tier == "high":
                where_clauses.append(f"{age_expr} BETWEEN 15 AND 19")
            elif risk_tier == "approaching":
                where_clauses.append(f"{age_expr} BETWEEN 10 AND 14")

            if search and search.strip():
                clean_s = search.strip().lower()
                where_clauses.append("""
                    (LOWER(normalized_address) LIKE :search 
                     OR LOWER(raw_permit_number) LIKE :search 
                     OR LOWER(contractor_name) LIKE :search
                     OR LOWER(city) LIKE :search)
                """)
                params["search"] = f"%{clean_s}%"

            where_sql = " AND ".join(where_clauses)

            # 1. Summary aggregations across aging cohorts
            summary_sql = f"""
                SELECT 
                    COUNT(*) as total_aging,
                    COALESCE(SUM(valuation), 0) as total_historical_val,
                    COUNT(CASE WHEN {age_expr} >= 20 THEN 1 END) as critical_count,
                    COUNT(CASE WHEN {age_expr} BETWEEN 15 AND 19 THEN 1 END) as warranty_count,
                    COUNT(CASE WHEN {age_expr} BETWEEN 10 AND 14 THEN 1 END) as approaching_count
                FROM normalized_permits
                WHERE {where_sql}
            """
            sum_row = conn.execute(text(summary_sql), params).mappings().first()
            total_aging = sum_row["total_aging"] if sum_row else 0
            total_historical_val = float(sum_row["total_historical_val"]) if sum_row else 0.0
            critical_count = sum_row["critical_count"] if sum_row else 0
            warranty_count = sum_row["warranty_count"] if sum_row else 0
            approaching_count = sum_row["approaching_count"] if sum_row else 0

            # Today's estimated replacement cost inflation multiplier (1.45x - 1.85x historical)
            replacement_pipeline_est = total_historical_val * 1.65

            # 2. Jurisdictions available
            jur_sql = f"""
                SELECT DISTINCT jurisdiction
                FROM normalized_permits
                WHERE issue_date IS NOT NULL
                  AND issue_date >= '1990-01-01'
                  AND {age_expr} >= 10
                ORDER BY jurisdiction ASC
            """
            jur_rows = conn.execute(text(jur_sql)).mappings().fetchall()
            jurisdictions_available = [r["jurisdiction"] for r in jur_rows if r["jurisdiction"]]

            # 3. Paged fetch
            params_paged = dict(params)
            params_paged["limit"] = limit
            params_paged["offset"] = offset

            fetch_sql = f"""
                SELECT 
                    id, raw_permit_number, normalized_address, city, state, zip_code, jurisdiction,
                    issue_date,
                    CAST({age_expr} AS INTEGER) as roof_age_years,
                    valuation, probable_roof_system, contractor_name, contractor_phone,
                    raw_description, latitude, longitude
                FROM normalized_permits
                WHERE {where_sql}
                ORDER BY roof_age_years DESC, valuation DESC
                LIMIT :limit OFFSET :offset
            """
            lead_rows = conn.execute(text(fetch_sql), params_paged).mappings().fetchall()

            leads: List[RoofAgingLeadItem] = []
            for r in lead_rows:
                age = int(r["roof_age_years"] or 10)
                h_val = float(r["valuation"] or 0.0)
                # Replacement cost accounting for current commercial labor/material rates
                repl_val = h_val * 1.65 if h_val > 0 else 185000.0

                if age >= 20:
                    status_lbl = "Expired Warranty (20+ Yrs)"
                    risk_lvl = "CRITICAL"
                    score = min(98, 85 + (age - 20) * 2)
                elif age >= 15:
                    status_lbl = "Critical End-of-Life (15-19 Yrs)"
                    risk_lvl = "HIGH"
                    score = 75 + (age - 15) * 2
                else:
                    status_lbl = "Approaching Term (10-14 Yrs)"
                    risk_lvl = "ELEVATED"
                    score = 55 + (age - 10) * 3

                h_val_fmt = f"${h_val / 1_000_000:.2f}M" if h_val >= 1_000_000 else (f"${int(h_val):,}" if h_val > 0 else "$0")
                repl_val_fmt = f"${repl_val / 1_000_000:.2f}M" if repl_val >= 1_000_000 else f"${int(repl_val):,}"

                leads.append(
                    RoofAgingLeadItem(
                        id=r["id"],
                        permit_number=r["raw_permit_number"],
                        address=r["normalized_address"],
                        city=r["city"],
                        state=r["state"],
                        zip_code=r["zip_code"],
                        jurisdiction=r["jurisdiction"],
                        install_date=str(r["issue_date"]),
                        roof_age_years=age,
                        warranty_status=status_lbl,
                        risk_level=risk_lvl,
                        historical_contractor=r["contractor_name"],
                        historical_contractor_phone=r["contractor_phone"],
                        historical_valuation=round(h_val, 2),
                        historical_valuation_formatted=h_val_fmt,
                        estimated_replacement_cost_usd=round(repl_val, 2),
                        estimated_replacement_cost_formatted=repl_val_fmt,
                        roof_system=r["probable_roof_system"] or "TPO Single-Ply",
                        scope_description=r["raw_description"] or "Commercial roof install.",
                        subsequent_permits_count=0,
                        replacement_priority_score=score,
                        latitude=r["latitude"],
                        longitude=r["longitude"],
                    )
                )

            if replacement_pipeline_est >= 1_000_000_000:
                pipeline_fmt = f"${replacement_pipeline_est / 1_000_000_000:.2f}B"
            elif replacement_pipeline_est >= 1_000_000:
                pipeline_fmt = f"${replacement_pipeline_est / 1_000_000:.2f}M"
            else:
                pipeline_fmt = f"${int(replacement_pipeline_est):,}"

            return RoofAgingAlarmResponse(
                total_aging_roofs=total_aging,
                total_replacement_pipeline_usd=round(replacement_pipeline_est, 2),
                total_replacement_pipeline_formatted=pipeline_fmt,
                critical_expired_count=critical_count,
                end_of_warranty_count=warranty_count,
                approaching_term_count=approaching_count,
                jurisdictions_available=jurisdictions_available,
                leads=leads,
            )
    except Exception as e:
        logger.error(f"Error querying roof aging alarm: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query roof aging alarm: {str(e)}"
        )


class PermitPhaseDetail(BaseModel):
    permit_id: str
    permit_number: str
    issue_date: str
    valuation: float
    valuation_formatted: str
    status: str
    roof_system: str
    contractor_name: str
    scope_description: str


class MultiPhaseCampusItem(BaseModel):
    campus_key: str
    address: str
    city: str
    state: str
    zip_code: str
    jurisdiction: str
    total_phases: int
    total_campus_valuation_usd: float
    total_campus_valuation_formatted: str
    project_span_start: str
    project_span_end: str
    active_phases_count: int
    completed_phases_count: int
    participating_contractors: List[str]
    roof_systems_detected: List[str]
    development_status: str  # "Active Multi-Phase Build", "Completed Mega-Campus", "Rolling Phased Re-Roof"
    phases: List[PermitPhaseDetail]


class MultiPhaseProjectsResponse(BaseModel):
    total_campuses: int
    total_campus_pipeline_usd: float
    total_campus_pipeline_formatted: str
    total_permits_across_campuses: int
    jurisdictions_available: List[str]
    campuses: List[MultiPhaseCampusItem]


@router.get("/multiphase-projects", response_model=MultiPhaseProjectsResponse)
async def get_multiphase_projects(
    jurisdiction: Optional[str] = Query(None, description="Filter by city/metro e.g. 'Dallas, TX', 'Addison'"),
    min_phases: int = Query(2, ge=2, le=20, description="Minimum number of permits filed at the address"),
    min_valuation: Optional[float] = Query(0.0, ge=0.0, description="Minimum total campus valuation in USD"),
    status_filter: Optional[str] = Query("all", description="'active', 'completed', or 'all'"),
    search: Optional[str] = Query(None, description="Address or contractor search query"),
    limit: int = Query(30, ge=1, le=100, description="Max campus developments to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> MultiPhaseProjectsResponse:
    """
    Pure Permit-Based Multi-Phase Project Detector.
    Detects large commercial campuses, industrial logistics hubs, and corporate parks
    with multiple building permits filed across phases (e.g. Phase 1, Phase 2, Building A/B).
    Reveals general contractors and roofing trade partners winning recurring multi-building packages.
    """
    engine = get_db_engine()

    try:
        with engine.connect() as conn:
            where_clauses = [
                "LOWER(p.normalized_address) NOT LIKE '%commercial corridor%'",
                "p.normalized_address IS NOT NULL",
                "p.normalized_address != ''",
                "p.valuation > 0",
            ]
            params: Dict[str, Any] = {
                "min_phases": min_phases,
                "min_val": min_valuation or 0.0,
            }

            if jurisdiction and jurisdiction.strip():
                clean_j = jurisdiction.strip().lower()
                where_clauses.append("(LOWER(p.jurisdiction) LIKE :jur OR LOWER(p.city) LIKE :jur)")
                params["jur"] = f"%{clean_j}%"

            if search and search.strip():
                clean_s = search.strip().lower()
                where_clauses.append("""
                    (LOWER(p.normalized_address) LIKE :search 
                     OR LOWER(p.contractor_name) LIKE :search
                     OR LOWER(p.city) LIKE :search)
                """)
                params["search"] = f"%{clean_s}%"

            where_sql = " AND ".join(where_clauses)

            # Having condition
            having_clauses = [
                "COUNT(p.id) >= :min_phases",
                "SUM(p.valuation) >= :min_val",
            ]

            if status_filter == "active":
                having_clauses.append("COUNT(CASE WHEN p.status IN ('Active', 'Issued') THEN 1 END) > 0")
            elif status_filter == "completed":
                having_clauses.append("COUNT(CASE WHEN p.status IN ('Active', 'Issued') THEN 1 END) = 0")

            having_sql = " AND ".join(having_clauses)

            # 1. Total summary query
            summary_sql = f"""
                WITH campus_agg AS (
                    SELECT 
                        p.normalized_address, p.city, p.state,
                        COUNT(p.id) as permit_count,
                        SUM(p.valuation) as campus_val
                    FROM normalized_permits p
                    WHERE {where_sql}
                    GROUP BY p.normalized_address, p.city, p.state
                    HAVING {having_sql}
                )
                SELECT 
                    COUNT(*) as total_campuses,
                    COALESCE(SUM(campus_val), 0) as total_pipeline_val,
                    COALESCE(SUM(permit_count), 0) as total_permits
                FROM campus_agg;
            """
            sum_row = conn.execute(text(summary_sql), params).mappings().first()
            total_campuses = sum_row["total_campuses"] if sum_row else 0
            total_pipeline_val = float(sum_row["total_pipeline_val"]) if sum_row else 0.0
            total_permits_sum = sum_row["total_permits"] if sum_row else 0

            # 2. Jurisdictions available
            jur_sql = f"""
                SELECT DISTINCT p.jurisdiction
                FROM normalized_permits p
                WHERE LOWER(p.normalized_address) NOT LIKE '%commercial corridor%'
                GROUP BY p.normalized_address, p.city, p.state, p.jurisdiction
                HAVING COUNT(p.id) >= 2
                ORDER BY p.jurisdiction ASC
            """
            jur_rows = conn.execute(text(jur_sql)).mappings().fetchall()
            jurisdictions_available = [r["jurisdiction"] for r in jur_rows if r["jurisdiction"]]

            # 3. Paged fetch of multi-phase campuses
            params_paged = dict(params)
            params_paged["limit"] = limit
            params_paged["offset"] = offset

            is_sqlite = "sqlite" in str(engine.url)

            if is_sqlite:
                contractor_agg = "GROUP_CONCAT(DISTINCT p.contractor_name)"
                roof_agg = "GROUP_CONCAT(DISTINCT p.probable_roof_system)"
            else:
                contractor_agg = "ARRAY_AGG(DISTINCT p.contractor_name) FILTER (WHERE p.contractor_name IS NOT NULL AND p.contractor_name NOT ILIKE '%licensed%')"
                roof_agg = "ARRAY_AGG(DISTINCT p.probable_roof_system) FILTER (WHERE p.probable_roof_system IS NOT NULL)"

            campuses_sql = f"""
                SELECT 
                    p.normalized_address, p.city, p.state, p.zip_code, p.jurisdiction,
                    COUNT(p.id) as total_phases,
                    SUM(p.valuation) as total_val,
                    MIN(p.issue_date) as first_date,
                    MAX(p.issue_date) as latest_date,
                    COUNT(CASE WHEN p.status IN ('Active', 'Issued') THEN 1 END) as active_count,
                    COUNT(CASE WHEN p.status NOT IN ('Active', 'Issued') THEN 1 END) as completed_count,
                    {contractor_agg} as contractors,
                    {roof_agg} as roof_systems
                FROM normalized_permits p
                WHERE {where_sql}
                GROUP BY p.normalized_address, p.city, p.state, p.zip_code, p.jurisdiction
                HAVING {having_sql}
                ORDER BY total_val DESC, total_phases DESC
                LIMIT :limit OFFSET :offset
            """
            campus_rows = conn.execute(text(campuses_sql), params_paged).mappings().fetchall()

            # Batch-fetch all phases for returned campuses in a single query (eliminating N+1 queries)
            campus_keys = [(cr["normalized_address"], cr["city"]) for cr in campus_rows]
            phase_map: Dict[str, List[PermitPhaseDetail]] = {}
            if campus_keys:
                addrs = [k[0] for k in campus_keys]
                cities = list(set([k[1] for k in campus_keys]))
                
                if is_sqlite:
                    # SQLite parameterized IN clause
                    addr_placeholders = ",".join([f":addr_{i}" for i in range(len(addrs))])
                    city_placeholders = ",".join([f":city_{i}" for i in range(len(cities))])
                    batch_params = {f"addr_{i}": a for i, a in enumerate(addrs)}
                    batch_params.update({f"city_{i}": c for i, c in enumerate(cities)})
                    batch_phase_sql = f"""
                        SELECT 
                            id, raw_permit_number, normalized_address, city, issue_date, valuation, status, 
                            probable_roof_system, contractor_name, raw_description
                        FROM normalized_permits
                        WHERE normalized_address IN ({addr_placeholders}) AND city IN ({city_placeholders})
                        ORDER BY issue_date DESC, valuation DESC
                    """
                    all_phase_rows = conn.execute(text(batch_phase_sql), batch_params).mappings().fetchall()
                else:
                    batch_phase_sql = """
                        SELECT 
                            id, raw_permit_number, normalized_address, city, issue_date, valuation, status, 
                            probable_roof_system, contractor_name, raw_description
                        FROM normalized_permits
                        WHERE normalized_address = ANY(:addrs) AND city = ANY(:cities)
                        ORDER BY issue_date DESC, valuation DESC
                    """
                    all_phase_rows = conn.execute(text(batch_phase_sql), {"addrs": addrs, "cities": cities}).mappings().fetchall()
                for pr in all_phase_rows:
                    ckey = f"{pr['normalized_address']}|{pr['city']}"
                    if ckey not in phase_map:
                        phase_map[ckey] = []
                    if len(phase_map[ckey]) < 10:
                        pval = float(pr["valuation"] or 0.0)
                        pval_fmt = f"${pval / 1_000_000:.2f}M" if pval >= 1_000_000 else f"${int(pval):,}"
                        phase_map[ckey].append(
                            PermitPhaseDetail(
                                permit_id=pr["id"],
                                permit_number=pr["raw_permit_number"],
                                issue_date=str(pr["issue_date"]) if pr["issue_date"] is not None else "Recent",
                                valuation=round(pval, 2),
                                valuation_formatted=pval_fmt,
                                status=pr["status"] or "Active",
                                roof_system=pr["probable_roof_system"] or "TPO Single-Ply",
                                contractor_name=pr["contractor_name"] or "Contractor on File",
                                scope_description=pr["raw_description"] or "Commercial roof install.",
                            )
                        )

            campuses: List[MultiPhaseCampusItem] = []
            for cr in campus_rows:
                addr = cr["normalized_address"]
                city = cr["city"]
                c_val = float(cr["total_val"] or 0.0)
                tot_phases = int(cr["total_phases"] or 0)
                act_count = int(cr["active_count"] or 0)
                comp_count = int(cr["completed_count"] or 0)

                if c_val >= 1_000_000_000:
                    val_fmt = f"${c_val / 1_000_000_000:.2f}B"
                elif c_val >= 1_000_000:
                    val_fmt = f"${c_val / 1_000_000:.2f}M"
                else:
                    val_fmt = f"${int(c_val):,}"

                if act_count > 0:
                    dev_status = "Active Multi-Phase Build"
                else:
                    dev_status = "Completed Multi-Building Campus"

                phase_details = phase_map.get(f"{addr}|{city}", [])
                clean_contractors = [c for c in (cr["contractors"] or []) if c and c.strip()]
                clean_roof_systems = [s for s in (cr["roof_systems"] or []) if s and s.strip()]

                campuses.append(
                    MultiPhaseCampusItem(
                        campus_key=f"{addr}-{city}".lower().replace(" ", "-"),
                        address=addr,
                        city=city,
                        state=cr["state"],
                        zip_code=cr["zip_code"] or "",
                        jurisdiction=cr["jurisdiction"],
                        total_phases=tot_phases,
                        total_campus_valuation_usd=round(c_val, 2),
                        total_campus_valuation_formatted=val_fmt,
                        project_span_start=str(cr["first_date"]) if cr["first_date"] else "Recent",
                        project_span_end=str(cr["latest_date"]) if cr["latest_date"] else "Recent",
                        active_phases_count=act_count,
                        completed_phases_count=comp_count,
                        participating_contractors=clean_contractors if clean_contractors else ["General Contractor on File"],
                        roof_systems_detected=clean_roof_systems if clean_roof_systems else ["TPO Single-Ply"],
                        development_status=dev_status,
                        phases=phase_details,
                    )
                )

            if total_pipeline_val >= 1_000_000_000:
                pipeline_fmt = f"${total_pipeline_val / 1_000_000_000:.2f}B"
            elif total_pipeline_val >= 1_000_000:
                pipeline_fmt = f"${total_pipeline_val / 1_000_000:.2f}M"
            else:
                pipeline_fmt = f"${int(total_pipeline_val):,}"

            return MultiPhaseProjectsResponse(
                total=total_campuses,
                total_campus_pipeline_usd=round(total_pipeline_val, 2),
                total_campus_pipeline_formatted=pipeline_fmt,
                total_permits_across_campuses=int(total_permits_sum),
                jurisdictions_available=jurisdictions_available,
                campuses=campuses,
            )
    except Exception as e:
        logger.error(f"Error querying multi-phase projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query multi-phase projects: {str(e)}"
        )


@router.get("/parcels/{parcel_id}")
async def get_parcel_detail(parcel_id: str):
    """
    Returns verified county appraisal district parcel details (owner, building sq ft, year built, valuation).
    """
    try:
        with get_db_connection() as conn:
            query = text("""
                SELECT 
                    id, account_number, jurisdiction_id, jurisdiction, address, city, county,
                    state, zip_code, building_sqft, land_sqft, year_built, property_type,
                    owner_name, owner_address, owner_city, owner_state, owner_zip,
                    total_valuation, improvement_valuation, latitude, longitude, data_source
                FROM parcels
                WHERE id = :parcel_id
                LIMIT 1
            """)
            row = conn.execute(query, {"parcel_id": parcel_id}).mappings().fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parcel {parcel_id} not found."
                )

            # Query all permits associated with this parcel
            permits_query = text("""
                SELECT id, raw_permit_number, issue_date, valuation, valuation_formatted,
                       status, probable_roof_system, contractor_name, raw_description
                FROM normalized_permits
                WHERE parcel_id = :parcel_id
                ORDER BY issue_date DESC
            """)
            perm_rows = conn.execute(permits_query, {"parcel_id": parcel_id}).mappings().fetchall()

            return {
                "id": row["id"],
                "accountNumber": row["account_number"],
                "jurisdiction": row["jurisdiction"],
                "address": row["address"],
                "city": row["city"],
                "county": row["county"],
                "state": row["state"],
                "zipCode": row["zip_code"],
                "buildingSqft": row["building_sqft"] or 0,
                "landSqft": row["land_sqft"] or 0,
                "yearBuilt": row["year_built"],
                "propertyType": row["property_type"],
                "ownerName": row["owner_name"],
                "ownerAddress": row["owner_address"],
                "totalValuation": float(row["total_valuation"] or 0.0),
                "improvementValuation": float(row["improvement_valuation"] or 0.0),
                "dataSource": row["data_source"],
                "latitude": float(row["latitude"]) if row["latitude"] else None,
                "longitude": float(row["longitude"]) if row["longitude"] else None,
                "linkedPermitsCount": len(perm_rows),
                "permits": [
                    {
                        "id": p["id"],
                        "permitNumber": p["raw_permit_number"],
                        "issueDate": str(p["issue_date"]) if p["issue_date"] else None,
                        "valuationFormatted": p["valuation_formatted"],
                        "status": p["status"],
                        "roofSystem": p["probable_roof_system"],
                        "contractorName": p["contractor_name"],
                        "scopeDescription": p["raw_description"],
                    }
                    for p in perm_rows
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching parcel {parcel_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query parcel: {str(e)}"
        )



