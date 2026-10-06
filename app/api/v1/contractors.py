from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, status

from app.schemas.contractor_schema import ContractorLeaderboardResponse, ContractorLeaderboardItem
from app.science.entity_resolution import build_contractor_leaderboard
from app.api.v1.permits import _PERMIT_WAREHOUSE

router = APIRouter(prefix="/contractors", tags=["Contractor Intelligence & Win Share"])


@router.get("/leaderboard", response_model=ContractorLeaderboardResponse)
async def get_contractor_leaderboard(
    jurisdiction: Optional[str] = Query(None, description="e.g. 'Dallas, TX' or 'Fort Worth, TX'"),
    limit: int = Query(50, ge=1, le=200, description="Max contractors to return"),
) -> ContractorLeaderboardResponse:
    """
    Computes deduplicated commercial roofing contractor rankings, captured market share,
    total permitted revenue volume, and primary roof membrane systems.
    Resolves noisy legal entity variations using RapidFuzz and state trade licenses.
    """
    all_permits = list(_PERMIT_WAREHOUSE.values())

    return build_contractor_leaderboard(
        permits=all_permits,
        jurisdiction_filter=jurisdiction,
        limit=limit,
    )
