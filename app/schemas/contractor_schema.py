from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ContractorLeaderboardItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    canonical_id: str = Field(..., alias="canonicalId")
    canonical_name: str = Field(..., alias="canonicalName")
    license_number: Optional[str] = Field(None, alias="licenseNumber")
    permit_count: int = Field(..., alias="permitCount")
    total_valuation_usd: float = Field(..., alias="totalValuationUSD")
    total_valuation_formatted: str = Field(..., alias="totalValuationFormatted")
    market_share_pct: float = Field(..., alias="marketSharePct")
    primary_roof_system: str = Field(..., alias="primaryRoofSystem")
    jurisdiction: str
    aliases: List[str] = []
    recent_permit_ids: List[str] = Field(default_factory=list, alias="recentPermitIds")


class ContractorLeaderboardResponse(BaseModel):
    total_contractors: int
    total_industry_valuation_usd: float
    jurisdiction_filter: Optional[str] = None
    leaderboard: List[ContractorLeaderboardItem]
