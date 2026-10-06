from fastapi import APIRouter
from app.extraction.noaa_client import NOAAClient
from app.schemas.storm_schema import GeoJSONFeatureCollection

router = APIRouter(prefix="/storms", tags=["Storm Intelligence"])

_noaa_client = NOAAClient()


@router.get("/active-swaths", response_model=GeoJSONFeatureCollection)
async def get_active_storm_swaths() -> GeoJSONFeatureCollection:
    """
    Returns active severe convective hail storm swaths as standard GeoJSON
    FeatureCollections with Dual-Pol radar metrics and kinetic energy contours.
    Consumable directly by Leaflet / Mapbox GIS layers.
    """
    return _noaa_client.get_canonical_swaths()
