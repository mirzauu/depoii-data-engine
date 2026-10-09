from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ScorePillar(BaseModel):
    name: str
    weight_score: float
    status: str  # "STRONG", "MODERATE", "LOW", "NEUTRAL"
    metric_value: str
    justification: str


class LeadDossier(BaseModel):
    parcel_id: str
    address: str
    city: str
    state: str
    zip_code: str
    owner_name: str
    property_type: str
    building_sqft: int
    year_built: Optional[int] = None
    cad_total_valuation: float

    # Meteorological Storm Impact
    storm_id: str
    storm_name: str
    event_date: str
    max_hail_inches: float
    max_gust_mph: float
    kinetic_energy_joules: float
    terminal_velocity_mph: float
    damage_severity_tier: str

    # Financial Scale Projections (NRCA Heuristic)
    estimated_replacement_low: float
    estimated_replacement_high: float
    estimated_replacement_mid: float
    estimated_replacement_formatted: str

    # Scoring & Classification
    unresolved_exposure_score: int  # 60 - 99
    lead_classification: str        # "TIER_1_HOT_LEAD" | "TIER_2_QUALIFIED" | "DEPRIORITIZED"
    lead_badge: str

    # 5-Pillar Score Breakdown
    scorecard_pillars: List[ScorePillar]

    # Explicit Strengths vs Risks
    why_strong_reasons: List[str]
    why_weak_reasons: List[str]

    # Sales Playbook & Outreach Hooks
    cold_call_opening_hook: str
    insurance_urgency_angle: str
    recommended_inspection_offer: str
    recommended_roof_system: str

    # Full Formatted Markdown Dossier Text
    markdown_dossier: str
