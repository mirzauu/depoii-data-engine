from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Union

PermitSourceSystem = str
PermitRoofCategory = str
PermitStatus = str
ProbableRoofSystem = str



class DepoiiNormalizedPermitSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Canonical ID: e.g. DEP-TX-DAL-COM-ROOF-26-000300")
    source_system: PermitSourceSystem = Field(..., alias="sourceSystem")
    raw_permit_number: str = Field(..., alias="rawPermitNumber")
    jurisdiction: str
    state: str
    county: Optional[str] = None
    issue_date: str = Field(..., alias="issueDate")
    applied_date: Optional[str] = Field(None, alias="appliedDate")
    expiration_date: Optional[str] = Field(None, alias="expirationDate")
    status: PermitStatus

    # Location
    normalized_address: str = Field(..., alias="normalizedAddress")
    city: str
    zip_code: str = Field(..., alias="zipCode")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    parcel_id: Optional[str] = Field(None, alias="parcelId")

    # Commercial Valuation & Scope
    valuation: float
    valuation_formatted: str = Field(..., alias="valuationFormatted")
    category: PermitRoofCategory
    raw_description: str = Field(..., alias="rawDescription")
    square_footage: Optional[int] = Field(None, alias="squareFootage")
    probable_roof_system: ProbableRoofSystem = Field(..., alias="probableRoofSystem")

    # Contractor
    contractor_name: str = Field(..., alias="contractorName")
    contractor_license: Optional[str] = Field(None, alias="contractorLicense")
    contractor_phone: Optional[str] = Field(None, alias="contractorPhone")

    # Depoii Intelligence
    is_hail_storm_window: bool = Field(False, alias="isHailStormWindow")
    associated_storm_event: Optional[str] = Field(None, alias="associatedStormEvent")
    confidence_score: int = Field(100, alias="confidenceScore")
    normalized_at: str = Field(..., alias="normalizedAt")

    @field_validator("confidence_score", mode="before")
    @classmethod
    def parse_confidence_score(cls, v):
        if v is None:
            return 100
        if isinstance(v, float):
            return int(round(v * 100 if v <= 1.0 else v))
        return int(v)


class BatchNormalizationError(BaseModel):
    index: int
    raw_id: Optional[str] = Field(None, alias="rawId")
    error: str


class NormalizationBatchResultSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_processed: int = Field(..., alias="totalProcessed")
    total_normalized: int = Field(..., alias="totalNormalized")
    total_skipped: int = Field(..., alias="totalSkipped")
    total_valuation_usd: float = Field(..., alias="totalValuationUSD")
    jurisdiction: str
    source_system: PermitSourceSystem = Field(..., alias="sourceSystem")
    records: List[DepoiiNormalizedPermitSchema]
    errors: List[BatchNormalizationError] = []
    timestamp: str
