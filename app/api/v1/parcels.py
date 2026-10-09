from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel

from app.core.logging import logger
from app.extraction.tarrant_parcel_client import TarrantParcelClient
from app.extraction.dallas_parcel_client import DallasParcelClient
from app.science.parcel_seed import SEED_COMMERCIAL_PARCELS

router = APIRouter(prefix="/parcels", tags=["Commercial Property Parcels"])

_db_engine = None

def get_db_engine():
    global _db_engine
    if _db_engine is None:
        import os
        from app.config import settings
        from sqlalchemy import create_engine
        local_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "depoii_local.db")
        if settings.USE_LOCAL_DB and os.path.exists(local_db_path):
            _db_engine = create_engine(
                f"sqlite:///{local_db_path}",
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            _db_engine = create_engine(
                settings.SYNC_DATABASE_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 3},
            )
    return _db_engine

_tarrant_client = TarrantParcelClient()
_dallas_client = DallasParcelClient()
_PARCEL_CACHE: Dict[str, Dict[str, Any]] = {p["id"]: p for p in SEED_COMMERCIAL_PARCELS}


class ParcelResponse(BaseModel):
    id: str
    address: str
    city: str
    county: str
    state: str
    zip_code: str
    building_sqft: int
    land_sqft: Optional[int] = None
    year_built: Optional[int] = None
    property_type: str
    owner_name: str
    total_valuation: Optional[float] = None
    data_source: Optional[str] = None
    latitude: float
    longitude: float


class ParcelListResponse(BaseModel):
    total: int
    source: str
    parcels: List[ParcelResponse]


@router.get("/tarrant", response_model=ParcelListResponse)
async def get_tarrant_parcels(
    min_sqft: int = Query(20000, description="Minimum building square footage"),
    city: Optional[str] = Query(None, description="Filter city (e.g., 'Fort Worth', 'Arlington')"),
    limit: int = Query(50, ge=1, le=200, description="Maximum parcels to return"),
) -> ParcelListResponse:
    """
    Harvests live commercial building parcels directly from Tarrant Appraisal District (TAD)
    ESRI ArcGIS REST MapServer at $0 external API cost.
    """
    try:
        results = await _tarrant_client.fetch_commercial_parcels(
            min_sqft=min_sqft,
            city_filter=city,
            limit=limit,
        )
        # Cache for spatial searches
        for p in results:
            _PARCEL_CACHE[p["id"]] = p

        return ParcelListResponse(
            total=len(results),
            source="Tarrant Appraisal District (ESRI ArcGIS REST)",
            parcels=results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed querying Tarrant County GIS: {str(e)}",
        )


@router.get("/dallas", response_model=ParcelListResponse)
async def get_dallas_parcels(
    min_sqft: int = Query(20000, description="Minimum building square footage"),
    city: Optional[str] = Query(None, description="Filter city (e.g., 'Dallas', 'Addison', 'Irving')"),
    limit: int = Query(50, ge=1, le=200, description="Maximum parcels to return"),
) -> ParcelListResponse:
    """
    Harvests live commercial building parcels directly from Dallas Central Appraisal District (DCAD)
    ESRI ArcGIS REST FeatureServer at $0 external API cost.
    """
    try:
        results = await _dallas_client.fetch_commercial_parcels(
            min_sqft=min_sqft,
            city_filter=city,
            limit=limit,
        )
        for p in results:
            _PARCEL_CACHE[p["id"]] = p

        return ParcelListResponse(
            total=len(results),
            source="Dallas Central Appraisal District (ESRI ArcGIS REST)",
            parcels=results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed querying Dallas County GIS: {str(e)}",
        )


@router.get("", response_model=ParcelListResponse)
@router.get("/search", response_model=ParcelListResponse)
async def search_parcels(
    city: Optional[str] = Query(None, description="City filter (e.g. 'Dallas', 'Fort Worth', 'Arlington')"),
    county: Optional[str] = Query(None, description="County filter (e.g. 'Dallas County', 'Tarrant County')"),
    min_sqft: int = Query(20000, description="Minimum building sqft"),
    source: Optional[str] = Query(None, description="Data source filter (e.g. 'TAD' or 'DCAD')"),
    limit: int = Query(50, ge=1, le=200),
) -> ParcelListResponse:
    """
    Unified Commercial Property Parcel search directly from Supabase PostgreSQL.
    Searches across all appraisal districts (DCAD, TAD, etc.) with city, county, and size filters.
    """
    city_str = city if isinstance(city, str) else None
    county_str = county if isinstance(county, str) else None
    source_str = source if isinstance(source, str) else None
    min_sqft_val = min_sqft if isinstance(min_sqft, int) else 20000
    limit_val = limit if isinstance(limit, int) else 50

    # Try querying Supabase database first
    try:
        from sqlalchemy import text
        engine = get_db_engine()
        with engine.connect() as conn:
            where_clauses = ["(building_sqft >= :min_sqft OR land_sqft >= :min_sqft)"]
            params: Dict[str, Any] = {"min_sqft": min_sqft_val, "limit": limit_val}

            if city_str:
                where_clauses.append("UPPER(city) LIKE :city")
                params["city"] = f"%{city_str.upper()}%"
            if county_str:
                where_clauses.append("UPPER(county) LIKE :county")
                params["county"] = f"%{county_str.upper()}%"
            if source_str:
                where_clauses.append("UPPER(data_source) LIKE :source")
                params["source"] = f"%{source_str.upper()}%"

            is_sqlite = "sqlite" in str(engine.url)
            lat_expr = "COALESCE(latitude, 32.7767) as latitude" if is_sqlite else "COALESCE(ST_Y(geom_point), 32.7767) as latitude"
            lon_expr = "COALESCE(longitude, -96.7970) as longitude" if is_sqlite else "COALESCE(ST_X(geom_point), -96.7970) as longitude"
            order_expr = "total_valuation DESC" if is_sqlite else "total_valuation DESC NULLS LAST"

            query_sql = f"""
                SELECT 
                    id, address, city, COALESCE(county, 'Dallas County') as county,
                    state, zip_code, building_sqft, land_sqft, year_built,
                    property_type, owner_name, total_valuation, data_source,
                    {lat_expr}, {lon_expr}
                FROM parcels
                WHERE {' AND '.join(where_clauses)}
                ORDER BY {order_expr}, building_sqft DESC
                LIMIT :limit;
            """
            rows = conn.execute(text(query_sql), params).mappings().fetchall()

            if rows:
                parcels = [ParcelResponse(**dict(r)) for r in rows]
                return ParcelListResponse(
                    total=len(parcels),
                    source="Supabase PostgreSQL Commercial Parcel Warehouse (DFW Metro)",
                    parcels=parcels,
                )
    except Exception as e:
        logger.warning(f"[ParcelsAPI] DB search failed ({e}), falling back to memory cache.")

    # In-memory fallback
    all_parcels = list(_PARCEL_CACHE.values())
    filtered = []
    for p in all_parcels:
        if p.get("building_sqft", 0) < min_sqft and p.get("land_sqft", 0) < min_sqft:
            continue
        if city and city.upper() not in p.get("city", "").upper():
            continue
        filtered.append(p)

    filtered.sort(key=lambda x: x.get("building_sqft", 0), reverse=True)
    return ParcelListResponse(
        total=len(filtered[:limit]),
        source="Depoii Commercial Parcel Warehouse (In-Memory Cache)",
        parcels=filtered[:limit],
    )


@router.get("/dark-market/overdue")
async def get_dark_market_overdue_parcels(
    min_age: int = Query(15, description="Minimum building roof age in years"),
    min_sqft: int = Query(20000, description="Minimum building square footage"),
    limit: int = Query(50, ge=1, le=200, description="Maximum parcels to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Returns commercial parcels that are 15+ years old with ZERO permits pulled (Dark Market Overdue Roofs).
    """
    from app.api.v1.permits import get_db_engine
    from sqlalchemy import text
    from datetime import datetime, timezone
    try:
        current_year = datetime.now(timezone.utc).year
        cutoff_year = current_year - min_age

        engine = get_db_engine()
        with engine.connect() as conn:
            # Query parcels with 0 permits and year_built <= cutoff_year
            count_sql = text("""
                SELECT COUNT(DISTINCT pa.id)
                FROM parcels pa
                LEFT JOIN normalized_permits p ON pa.id = p.parcel_id
                WHERE pa.year_built IS NOT NULL 
                  AND pa.year_built <= :cutoff_year
                  AND pa.building_sqft >= :min_sqft
                  AND p.id IS NULL
            """)
            total_count = conn.execute(count_sql, {
                "cutoff_year": cutoff_year,
                "min_sqft": min_sqft
            }).scalar() or 0

            fetch_sql = text("""
                SELECT 
                    pa.id, pa.account_number, pa.jurisdiction, pa.address, pa.city,
                    pa.state, pa.zip_code, pa.building_sqft, pa.year_built, pa.property_type,
                    pa.owner_name, pa.total_valuation, pa.improvement_valuation, pa.data_source,
                    pa.latitude, pa.longitude
                FROM parcels pa
                LEFT JOIN normalized_permits p ON pa.id = p.parcel_id
                WHERE pa.year_built IS NOT NULL 
                  AND pa.year_built <= :cutoff_year
                  AND pa.building_sqft >= :min_sqft
                  AND p.id IS NULL
                ORDER BY pa.building_sqft DESC, pa.year_built ASC
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(fetch_sql, {
                "cutoff_year": cutoff_year,
                "min_sqft": min_sqft,
                "limit": limit,
                "offset": offset
            }).mappings().fetchall()

            overdue_list = []
            for r in rows:
                age = current_year - int(r["year_built"])
                b_sqft = int(r["building_sqft"] or 25000)
                # Commercial re-roof cost estimate baseline: $11.50 / sqft
                est_reroof_cost = round(b_sqft * 11.50, 2)
                if est_reroof_cost >= 1_000_000:
                    cost_fmt = f"${est_reroof_cost / 1_000_000:.2f}M"
                else:
                    cost_fmt = f"${int(est_reroof_cost):,}"

                urgency = "CRITICAL (Warranty Expired)" if age >= 25 else "HIGH (End of Life)" if age >= 20 else "MODERATE (Inspection Due)"

                overdue_list.append({
                    "parcelId": r["id"],
                    "address": r["address"],
                    "city": r["city"],
                    "state": r["state"],
                    "zipCode": r["zip_code"],
                    "jurisdiction": r["jurisdiction"],
                    "buildingSqft": b_sqft,
                    "buildingSqftFormatted": f"{b_sqft:,} sq ft",
                    "yearBuilt": r["year_built"],
                    "roofAgeYears": age,
                    "urgency": urgency,
                    "ownerName": r["owner_name"],
                    "propertyType": r["property_type"],
                    "estimatedReroofValuation": est_reroof_cost,
                    "estimatedReroofValuationFormatted": cost_fmt,
                    "totalPropertyValuation": float(r["total_valuation"] or 0.0),
                    "permitCount": 0,
                    "hasPermitHistory": False,
                    "outreachAngle": f"No municipal permit recorded since {r['year_built']} construction ({age} yrs old). Recommend full infrared moisture scan and warranty restoration.",
                    "dataSource": r["data_source"],
                })

            return {
                "total": total_count,
                "count": len(overdue_list),
                "minAge": min_age,
                "minSqft": min_sqft,
                "limit": limit,
                "offset": offset,
                "overdueParcels": overdue_list,
            }
    except Exception as e:
        logger.error(f"Error fetching dark market overdue parcels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query overdue parcels: {str(e)}"
        )


@router.get("/{parcel_id}")
async def get_single_parcel(parcel_id: str):
    """
    Returns verified parcel information and any linked historical permits.
    """
    from app.api.v1.permits import get_db_engine
    from sqlalchemy import text
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
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

