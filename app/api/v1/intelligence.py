from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.storm_schema import UnresolvedExposureTarget
from app.science.spatial_queries import evaluate_spatial_exposure_in_memory
from app.extraction.noaa_client import DFW_MAY28_SWATH_POLYGON
from app.science.parcel_seed import SEED_COMMERCIAL_PARCELS
from app.api.v1.permits import _PERMIT_WAREHOUSE

router = APIRouter(prefix="/intelligence", tags=["Commercial Intelligence"])


class UnresolvedExposureResponse(BaseModel):
    total_targets: int
    storm_name: str
    event_date: str
    max_hail_inches: float
    total_unresolved_valuation_mid: float
    targets: List[UnresolvedExposureTarget]


@router.get("/unresolved-exposure", response_model=UnresolvedExposureResponse)
async def get_unresolved_exposure(
    min_sqft: int = Query(50000, description="Minimum building square footage filter"),
    min_hail_inches: float = Query(1.75, description="Minimum hail diameter threshold"),
) -> UnresolvedExposureResponse:
    """
    Identifies high-value commercial building assets located inside severe hail swaths
    that have zero municipal repair permits filed.
    Generates actionable lead target pipeline with physical kinetic damage metrics.
    """
    storm_meta = {
        "storm_name": "May 28, 2024 Dallas Severe Hail Core",
        "event_date": "2024-05-28",
        "max_hail_inches": 2.50,
    }

    existing_permits = list(_PERMIT_WAREHOUSE.values())

    targets = evaluate_spatial_exposure_in_memory(
        parcels=SEED_COMMERCIAL_PARCELS,
        swath_polygon_coords=DFW_MAY28_SWATH_POLYGON,
        storm_metadata=storm_meta,
        existing_permits=existing_permits,
        min_sqft=min_sqft,
    )

    total_val_mid = sum(t.estimated_replacement_mid for t in targets)

    return UnresolvedExposureResponse(
        total_targets=len(targets),
        storm_name=storm_meta["storm_name"],
        event_date=storm_meta["event_date"],
        max_hail_inches=storm_meta["max_hail_inches"],
        total_unresolved_valuation_mid=round(total_val_mid, 2),
        targets=targets,
    )
