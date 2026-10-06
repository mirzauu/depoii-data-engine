from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class GeoJSONGeometry(BaseModel):
    type: str  # "Polygon" | "MultiPolygon" | "Point"
    coordinates: Any


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


class StormSwathSummary(BaseModel):
    id: str
    storm_name: str
    event_date: str
    max_hail_inches: float
    max_gust_mph: Optional[int] = None
    affected_jurisdiction: str
    state: str
    impacted_parcels_count: int
    unresolved_exposure_valuation_mid: float


class UnresolvedExposureTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    parcel_id: str = Field(..., alias="parcelId")
    address: str
    city: str
    zip_code: str = Field(..., alias="zipCode")
    state: str
    building_sqft: int = Field(..., alias="buildingSqft")
    year_built: Optional[int] = Field(None, alias="yearBuilt")
    property_type: str = Field("Commercial Warehouse", alias="propertyType")
    owner_name: str = Field(..., alias="ownerName")

    # Storm exposure details
    storm_name: str = Field(..., alias="stormName")
    event_date: str = Field(..., alias="eventDate")
    max_hail_inches: float = Field(..., alias="maxHailInches")
    kinetic_energy_joules: float = Field(..., alias="kineticEnergyJoules")

    # Predictive Replacement Range (NRCA Heuristic)
    estimated_replacement_low: float = Field(..., alias="estimatedReplacementLow")
    estimated_replacement_high: float = Field(..., alias="estimatedReplacementHigh")
    estimated_replacement_mid: float = Field(..., alias="estimatedReplacementMid")
    estimated_replacement_formatted: str = Field(..., alias="estimatedReplacementFormatted")

    # Repair permit status
    has_repair_permit: bool = Field(False, alias="hasRepairPermit")
    months_unrepaired: int = Field(..., alias="monthsUnrepaired")
    unresolved_exposure_score: int = Field(..., alias="unresolvedExposureScore")
    lead_tier: str = Field("TIER_1_ENTERPRISE", alias="leadTier")
