import json
from typing import List, Optional
from fastapi import APIRouter, Query
from sqlalchemy import create_engine, text

from app.extraction.noaa_client import NOAAClient
from app.extraction.hail_events_service import get_hail_events_catalog
from app.schemas.storm_schema import GeoJSONFeature, GeoJSONGeometry, GeoJSONFeatureCollection
from app.schemas.hail_events_schema import HailEventsCatalogResponse
from app.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/storms", tags=["Storm Intelligence"])

_noaa_client = NOAAClient()
_db_engine = None


def get_db_engine():
    global _db_engine
    if _db_engine is None:
        _db_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _db_engine


@router.get("/active-swaths", response_model=GeoJSONFeatureCollection)
async def get_active_storm_swaths() -> GeoJSONFeatureCollection:
    """
    Returns active severe convective hail storm swaths as standard GeoJSON
    FeatureCollections with Dual-Pol radar metrics and kinetic energy contours.
    Queries depoii_local.db SQLite and Supabase PostGIS storm_swaths.
    """
    # 1. First attempt to serve full expanded catalog from local SQLite DB
    try:
        import os
        import sqlite3
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        local_db_path = os.path.join(repo_root, "depoii_local.db")
        if os.path.exists(local_db_path):
            conn = sqlite3.connect(local_db_path)
            cur = conn.cursor()
            rows = cur.execute("""
                SELECT id, storm_name, event_date, max_hail_inches, max_gust_mph, jurisdiction_id, properties
                FROM storm_swaths
                ORDER BY event_date DESC
            """).fetchall()
            if rows:
                features = []
                for sid, sname, edate, max_hail, max_gust, jur_id, props_str in rows:
                    props = json.loads(props_str or "{}")
                    poly_coords = props.get("polygon") or []
                    if poly_coords and len(poly_coords) >= 3:
                        geom = GeoJSONGeometry(
                            type="Polygon",
                            coordinates=[poly_coords]
                        )
                    else:
                        continue
                    props.update({
                        "id": sid,
                        "storm_name": sname,
                        "event_date": str(edate),
                        "jurisdiction_id": jur_id,
                        "max_hail_inches": float(max_hail or 1.5),
                        "max_gust_mph": max_gust or 60,
                    })
                    features.append(
                        GeoJSONFeature(
                            geometry=geom,
                            properties=props
                        )
                    )
                conn.close()
                if features:
                    return GeoJSONFeatureCollection(features=features)
            conn.close()
    except Exception as exc:
        logger.warning(f"Local sqlite storm swaths query failed: {exc}")

    # 2. Fallback to Supabase PostGIS if available
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            sql = """
                SELECT 
                    id, 
                    storm_name, 
                    event_date, 
                    max_hail_inches, 
                    max_gust_mph, 
                    jurisdiction_id, 
                    ST_AsGeoJSON(geom_polygon) as geom_json, 
                    properties 
                FROM storm_swaths
                ORDER BY event_date DESC;
            """
            rows = conn.execute(text(sql)).mappings().fetchall()
            if rows:
                features = []
                for r in rows:
                    geom_dict = json.loads(r["geom_json"])
                    props = dict(r["properties"] or {})
                    props.update({
                        "id": r["id"],
                        "storm_name": r["storm_name"],
                        "event_date": str(r["event_date"]),
                        "jurisdiction_id": r["jurisdiction_id"],
                        "max_hail_inches": float(r["max_hail_inches"] or 1.5),
                        "max_gust_mph": r["max_gust_mph"] or 60,
                    })
                    features.append(
                        GeoJSONFeature(
                            geometry=GeoJSONGeometry(
                                type=geom_dict.get("type", "MultiPolygon"),
                                coordinates=geom_dict.get("coordinates", [])
                            ),
                            properties=props
                        )
                    )
                return GeoJSONFeatureCollection(features=features)
    except Exception as exc:
        logger.warning(f"Database storm swaths query failed, falling back to NOAA client: {exc}")

    return _noaa_client.get_canonical_swaths()


@router.get("/live-alerts")
async def get_live_weather_alerts(state: str = "TX"):
    """
    Queries live real-time National Weather Service (NWS / NOAA) severe weather alerts
    directly from api.weather.gov for the specified state.
    """
    return await _noaa_client.fetch_live_active_alerts(state=state)


@router.get("/hail-events", response_model=HailEventsCatalogResponse)
async def get_hail_events(
    state: str = Query("TX", description="Two-letter code. Start with TX."),
    since: str = Query("2024-03-01", description="Only reports on or after this date. The app currently uses 2024-03-01."),
    min_hail_inches: float = Query(1.5, description="Default 1.5. A day is kept only when the largest report is at least this big and there are at least two reports."),
    event_date: Optional[str] = Query(None, description="Optional YYYY-MM-DD. When set, include that day's report points and warning polygons. When omitted, do that for the newest event only.")
) -> HailEventsCatalogResponse:
    """
    Replaces the hail-report catalog that GET /api/live builds in the Next.js app.
    Groups NWS reports by calendar day in US Central time.
    Returns the newest 12 days passing filter, with selected event reports and warning polygons.
    """
    return await get_hail_events_catalog(
        state=state,
        since=since,
        min_hail_inches=min_hail_inches,
        event_date=event_date
    )


