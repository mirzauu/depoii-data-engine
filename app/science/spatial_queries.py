from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from shapely.geometry import Point, Polygon
from app.schemas.storm_schema import UnresolvedExposureTarget
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.extraction.noaa_client import calculate_hail_physics, DFW_MAY28_SWATH_POLYGON
from app.core.logging import logger

# NRCA 2024-2026 Commercial Roofing Replacement Cost Heuristics ($/sq ft)
NRCA_COST_PER_SQFT_LOW = 7.50
NRCA_COST_PER_SQFT_HIGH = 12.50
TEXAS_LABOR_INDEX = 0.94


def estimate_nrca_replacement_cost(sqft: int, state: str = "TX") -> Dict[str, Any]:
    """
    Computes an honest heuristic valuation range based on NRCA $/sq ft
    and RSMeans regional labor indices (Fix #5).
    """
    multiplier = TEXAS_LABOR_INDEX if state.upper() == "TX" else 1.00
    low = round(sqft * NRCA_COST_PER_SQFT_LOW * multiplier)
    high = round(sqft * NRCA_COST_PER_SQFT_HIGH * multiplier)
    mid = round((low + high) / 2.0)

    # Format human readable
    if mid >= 1_000_000:
        formatted = f"${low / 1_000_000:.2f}M – ${high / 1_000_000:.2f}M"
    else:
        formatted = f"${low:,} – ${high:,}"

    return {
        "low": float(low),
        "high": float(high),
        "mid": float(mid),
        "formatted": formatted,
    }


def calculate_months_unrepaired(event_date_str: str) -> int:
    try:
        event_dt = datetime.strptime(event_date_str, "%Y-%m-%d")
        now_dt = datetime.now()
        months = (now_dt.year - event_dt.year) * 12 + (now_dt.month - event_dt.month)
        return max(0, months)
    except Exception:
        return 24


def calculate_exposure_score(
    hail_inches: float,
    building_sqft: int,
    months_unrepaired: int,
    year_built: Optional[int] = None,
) -> int:
    """
    Multi-factor urgency formula:
    Score = Base (40) + Hail Severity + Scale Factor + Staleness Aging
    """
    score = 40.0
    # Hail diameter impact (1.5" = +15, 2.5" = +28)
    score += (hail_inches * 11.5)
    # Scale impact (large assets have higher priority for roofers)
    score += min(20.0, building_sqft / 15000.0)
    # Months unrepaired (longer window = greater risk of insulation water intrusion)
    score += min(15.0, months_unrepaired * 0.5)

    # Roof age vulnerability
    if year_built and year_built < 2005:
        score += 8.0

    return min(99, max(60, int(round(score))))


def get_postgis_unresolved_exposure_sql() -> str:
    """
    Returns the production PostGIS SQL query template (Fix #3).
    Executes directly in database using spatial GIST indices.
    """
    return """
    SELECT 
        p.id AS parcel_id,
        p.address,
        p.city,
        p.zip_code,
        p.state,
        p.building_sqft,
        p.year_built,
        p.property_type,
        p.owner_name,
        s.storm_name,
        s.event_date,
        s.max_hail_inches
    FROM parcels p
    JOIN storm_swaths s ON ST_Intersects(p.geom, s.geom)
    WHERE s.id = :storm_id
      AND s.max_hail_inches >= :min_hail
      AND p.building_sqft >= :min_sqft
      AND p.id NOT IN (
          SELECT DISTINCT np.parcel_id
          FROM normalized_permits np
          WHERE np.parcel_id IS NOT NULL
            AND np.issue_date >= s.event_date
            AND np.category IN ('Commercial Re-Roof', 'Roof Tear-Off & Replace')
      )
    ORDER BY p.building_sqft DESC
    LIMIT :limit;
    """


def evaluate_spatial_exposure_in_memory(
    parcels: List[Dict[str, Any]],
    swath_polygon_coords: List[List[float]],
    storm_metadata: Dict[str, Any],
    existing_permits: List[DepoiiNormalizedPermitSchema],
    min_sqft: int = 50000,
) -> List[UnresolvedExposureTarget]:
    """
    Spatial cross-reference engine:
    1. Tests polygon intersection between parcel coordinates and storm swath.
    2. Cross-references parcel address against normalized permits issued since the storm.
    3. Retains parcels with NO repair permits (Unresolved Exposure).
    """
    poly = Polygon(swath_polygon_coords)
    hail_inches = float(storm_metadata.get("max_hail_inches", 2.0))
    event_date = storm_metadata.get("event_date", "2024-05-28")
    storm_name = storm_metadata.get("storm_name", "May 28, 2024 Dallas Severe Hail Core")

    physics = calculate_hail_physics(hail_inches)
    months_unrepaired = calculate_months_unrepaired(event_date)

    # Build set of normalized permit addresses / parcel IDs that have repaired since the storm
    repaired_keys = set()
    for p in existing_permits:
        if p.issue_date >= event_date:
            if p.parcel_id:
                repaired_keys.add(p.parcel_id.strip().upper())
            repaired_keys.add(p.normalized_address.strip().upper())

    unresolved_targets: List[UnresolvedExposureTarget] = []

    for parcel in parcels:
        sqft = int(parcel.get("building_sqft", 0))
        if sqft < min_sqft:
            continue

        lat = float(parcel["latitude"])
        lon = float(parcel["longitude"])
        pt = Point(lon, lat)  # (x=lon, y=lat)

        # Check spatial containment
        if not poly.contains(pt):
            continue

        # Check if already repaired
        parcel_id = str(parcel["id"]).strip().upper()
        addr_clean = str(parcel["address"]).strip().upper()

        if parcel_id in repaired_keys or addr_clean in repaired_keys:
            # Property already captured / permitted — not unresolved
            continue

        valuation_info = estimate_nrca_replacement_cost(sqft, state=parcel.get("state", "TX"))
        score = calculate_exposure_score(
            hail_inches=hail_inches,
            building_sqft=sqft,
            months_unrepaired=months_unrepaired,
            year_built=parcel.get("year_built"),
        )

        tier = "TIER_1_ENTERPRISE" if sqft >= 150000 else "TIER_2_MIDMARKET"

        target = UnresolvedExposureTarget(
            parcelId=parcel["id"],
            address=parcel["address"],
            city=parcel["city"],
            zipCode=parcel["zip_code"],
            state=parcel["state"],
            buildingSqft=sqft,
            yearBuilt=parcel.get("year_built"),
            propertyType=parcel.get("property_type", "Commercial Warehouse"),
            ownerName=parcel["owner_name"],
            stormName=storm_name,
            eventDate=event_date,
            maxHailInches=hail_inches,
            kineticEnergyJoules=physics["kinetic_energy_joules"],
            estimatedReplacementLow=valuation_info["low"],
            estimatedReplacementHigh=valuation_info["high"],
            estimatedReplacementMid=valuation_info["mid"],
            estimatedReplacementFormatted=valuation_info["formatted"],
            hasRepairPermit=False,
            monthsUnrepaired=months_unrepaired,
            unresolvedExposureScore=score,
            leadTier=tier,
        )
        unresolved_targets.append(target)

    # Sort descending by building sqft
    unresolved_targets.sort(key=lambda t: t.building_sqft, reverse=True)
    return unresolved_targets
