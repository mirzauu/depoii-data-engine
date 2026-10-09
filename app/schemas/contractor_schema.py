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
    website_url: Optional[str] = Field(None, alias="websiteUrl")
    logo_url: Optional[str] = Field(None, alias="logoUrl")
    hq_address: Optional[str] = Field(None, alias="hqAddress")
    phone_number: Optional[str] = Field(None, alias="phoneNumber")
    year_founded: Optional[int] = Field(None, alias="yearFounded")
    crew_capacity_estimate: Optional[str] = Field(None, alias="crewCapacityEstimate")
    manufacturer_certifications: List[str] = Field(default_factory=list, alias="manufacturerCertifications")
    leadership: List[dict] = Field(default_factory=list)
    m_and_a_profile: Optional[dict] = Field(None, alias="mAndAProfile")


class ContractorLeaderboardResponse(BaseModel):
    total_contractors: int
    total_industry_valuation_usd: float
    jurisdiction_filter: Optional[str] = None
    leaderboard: List[ContractorLeaderboardItem]
