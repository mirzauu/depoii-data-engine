from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from collections import Counter, defaultdict

from app.api.v1.permits import _PERMIT_WAREHOUSE
from app.science.parcel_seed import SEED_COMMERCIAL_PARCELS

router = APIRouter(prefix="/locations", tags=["Location Hierarchy & Coverage"])

US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}

TARRANT_CITIES = {
    "FORT WORTH", "ARLINGTON", "KELLER", "MANSFIELD", "SOUTHLAKE", "EULESS",
    "BEDFORD", "GRAPEVINE", "HALTOM CITY", "NORTH RICHLAND HILLS", "HURST",
}

DALLAS_COUNTY_CITIES = {
    "DALLAS", "CARROLLTON", "FARMERS BRANCH", "ADDISON", "IRVING", "PLANO",
    "RICHARDSON", "GARLAND", "MESQUITE", "COPPELL", "GRAND PRAIRIE",
}

DFW_METRO_CITIES = TARRANT_CITIES | DALLAS_COUNTY_CITIES


def _evaluate_parcel_coverage(state: str, city: str) -> tuple[bool, Optional[str]]:
    city_upper = city.strip().upper()
    if state == "TX":
        if city_upper in TARRANT_CITIES:
            return True, "Tarrant Appraisal District (Live ESRI GIS)"
        if city_upper in DALLAS_COUNTY_CITIES:
            return True, "Dallas County CAD / Seeded Commercial"
    return False, None


def _evaluate_storm_coverage(state: str, city: str) -> tuple[bool, Optional[str]]:
    city_upper = city.strip().upper()
    if state == "TX" and city_upper in DFW_METRO_CITIES:
        return True, 'DFW Severe Hail Corridor (May 28 - 2.50" MESH)'
    return False, None


CITY_METADATA_CATALOG = {
    "TX-DALLAS": {
        "portal_url": "https://aca-prod.accela.com/dallas",
        "cad_portal_url": "https://www.dallascad.org/SearchOption.aspx",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.7767, "lng": -96.7970
    },
    "TX-FORT_WORTH": {
        "portal_url": "https://aca-prod.accela.com/CFW",
        "cad_portal_url": "https://www.tad.org/",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.7555, "lng": -97.3308
    },
    "TX-ADDISON": {
        "portal_url": "https://addisontx-energovweb.tylerhost.net/apps/selfservice#/search",
        "cad_portal_url": "https://www.dallascad.org",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.9618, "lng": -96.8292
    },
    "TX-CARROLLTON": {
        "portal_url": "https://www.cityofcarrollton.com/departments/departments-a-f/building-inspection",
        "cad_portal_url": "https://www.dallascad.org",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.9538, "lng": -96.8903
    },
    "TX-FARMERS_BRANCH": {
        "portal_url": "https://www.farmersbranchtx.gov/306/Building-Inspection",
        "cad_portal_url": "https://www.dallascad.org",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.9265, "lng": -96.8961
    },
    "TX-KELLER": {
        "portal_url": "https://www.cityofkeller.com/services/community-development/building-services",
        "cad_portal_url": "https://www.tad.org/",
        "metro_area": "Dallas-Fort Worth Metroplex",
        "lat": 32.9342, "lng": -97.2295
    },
    "TX-AUSTIN": {
        "portal_url": "https://data.austintexas.gov/Building-and-Development/Building-and-Demolition-Permits/3syk-w9eu",
        "cad_portal_url": "https://www.traviscad.org/",
        "metro_area": "Austin-Round Rock Metro",
        "lat": 30.2672, "lng": -97.7431
    },
    "OH-CINCINNATI": {
        "portal_url": "https://data.cincinnati-oh.gov/Thriving-Neighborhoods/Buildings-Permits-Commercial-and-Residential/2c85-m678",
        "cad_portal_url": "https://wedge.hcauditor.org/",
        "metro_area": "Cincinnati Metropolitan Area",
        "lat": 39.1031, "lng": -84.5120
    },
    "WA-SEATTLE": {
        "portal_url": "https://data.seattle.gov/Permitting/Building-Permits/i5jq-ms7b",
        "cad_portal_url": "https://blue.kingcounty.com/Assessor/eRealProperty",
        "metro_area": "Seattle-Tacoma-Bellevue Metro",
        "lat": 47.6062, "lng": -122.3321
    },
    "FL-GAINESVILLE": {
        "portal_url": "https://data.cityofgainesville.org/Building-Development/Building-Permits/btya-7q4v",
        "cad_portal_url": "https://www.acpafl.org/",
        "metro_area": "Gainesville Metro",
        "lat": 29.6516, "lng": -82.3248
    },
    "NY-NEW_YORK_CITY": {
        "portal_url": "https://data.cityofnewyork.us/Housing-Development/DOB-Permit-Issuance/ipu4-2q9a",
        "cad_portal_url": "https://a836-acris.nyc.gov/",
        "metro_area": "New York Metropolitan Area",
        "lat": 40.7128, "lng": -74.0060
    },
    "LA-BATON_ROUGE": {
        "portal_url": "https://data.brla.gov/Government-Administration/Building-Permits/26w4-r6ws",
        "cad_portal_url": "https://www.ebrpa.org/",
        "metro_area": "Baton Rouge Metro",
        "lat": 30.4515, "lng": -91.1871
    },
    "CA-SONOMA_COUNTY": {
        "portal_url": "https://sonomacounty.ca.gov/Permit-Sonoma/",
        "cad_portal_url": "https://sonomacounty.ca.gov/Auditor-Controller-Treasurer-Tax-Collector/",
        "metro_area": "San Francisco Bay Area - North Bay",
        "lat": 38.2919, "lng": -122.4580
    },
    "IL-CHICAGO": {
        "portal_url": "https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu",
        "cad_portal_url": "https://www.cookcountyassessor.com/",
        "metro_area": "Chicago Metropolitan Area",
        "lat": 41.8781, "lng": -87.6298
    },
    "MA-CAMBRIDGE": {
        "portal_url": "https://data.cambridgema.gov/Inspectional-Services/Building-Permits/j2mk-n7h9",
        "cad_portal_url": "https://www.cambridgema.gov/assessing",
        "metro_area": "Greater Boston Metro",
        "lat": 42.3736, "lng": -71.1097
    },
    "MA-FRAMINGHAM": {
        "portal_url": "https://www.framinghamma.gov/224/Inspectional-Services",
        "cad_portal_url": "https://framinghamma.gov/assessor",
        "metro_area": "Greater Boston Metro",
        "lat": 42.2793, "lng": -71.4162
    },
}


class CityHierarchyItem(BaseModel):
    city: str
    state: str
    permit_count: int
    total_valuation_usd: float
    roof_categories: Dict[str, int]
    top_contractors: List[Dict[str, Any]]
    parcel_coverage: bool
    parcel_source: Optional[str] = None
    has_active_storms: bool
    storm_details: Optional[str] = None
    portal_url: Optional[str] = None
    cad_portal_url: Optional[str] = None
    metro_area: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class StateHierarchyItem(BaseModel):
    state_code: str
    state_name: str
    total_permits: int
    total_valuation_usd: float
    city_count: int
    has_parcel_coverage: bool
    has_active_storms: bool
    cities: List[CityHierarchyItem]


class LocationHierarchyResponse(BaseModel):
    total_states: int
    total_cities: int
    total_permits: int
    total_valuation_usd: float
    states: List[StateHierarchyItem]


class StateSummaryItem(BaseModel):
    state_code: str
    state_name: str
    total_permits: int
    total_valuation_usd: float
    city_count: int
    has_parcel_coverage: bool
    has_active_storms: bool


def _build_location_data(state_filter: Optional[str] = None, min_permits: int = 1) -> Dict[str, Dict[str, Any]]:
    """
    Aggregates the in-memory permit warehouse grouped by State -> City.
    """
    state_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "cities": defaultdict(lambda: {
            "permits": 0,
            "valuation": 0.0,
            "categories": Counter(),
            "contractors": Counter(),
            "lat": None,
            "lng": None,
        })
    })

    # Also harvest coordinates from seed parcels if any
    seed_coords: Dict[tuple[str, str], tuple[float, float]] = {}
    for p in SEED_COMMERCIAL_PARCELS:
        s = p.get("state", "TX").upper().strip()
        c = p.get("city", "").title().strip()
        if p.get("latitude") and p.get("longitude"):
            seed_coords[(s, c)] = (p["latitude"], p["longitude"])

    for p in _PERMIT_WAREHOUSE.values():
        st = p.state.strip().upper()
        if state_filter and st != state_filter.strip().upper():
            continue

        ct = p.city.strip().title()
        entry = state_data[st]["cities"][ct]
        entry["permits"] += 1
        entry["valuation"] += p.valuation
        entry["categories"][p.category] += 1

        if p.contractor_name and p.contractor_name.strip() and p.contractor_name.strip().upper() != "UNKNOWN":
            entry["contractors"][p.contractor_name.strip()] += 1

        if entry["lat"] is None and p.latitude:
            entry["lat"] = p.latitude
            entry["lng"] = p.longitude

    # Fill coords from seeds if missing
    for (st, ct), (lat, lng) in seed_coords.items():
        if st in state_data and ct in state_data[st]["cities"]:
            if state_data[st]["cities"][ct]["lat"] is None:
                state_data[st]["cities"][ct]["lat"] = lat
                state_data[st]["cities"][ct]["lng"] = lng

    return state_data


@router.get("/hierarchy", response_model=LocationHierarchyResponse)
async def get_location_hierarchy(
    state: Optional[str] = Query(None, description="Optional 2-letter state code filter (e.g. TX, OH, FL)"),
    min_permits: int = Query(1, ge=1, description="Minimum permit threshold per city"),
) -> LocationHierarchyResponse:
    """
    Returns full hierarchical breakdown of all jurisdictions organized strictly by State -> City.
    Aggregates permit volumes, total commercial valuation, parcel data availability, and weather intelligence.
    """
    min_p = min_permits if isinstance(min_permits, int) else 1
    raw_data = _build_location_data(state_filter=state, min_permits=min_p)

    state_items: List[StateHierarchyItem] = []
    overall_total_permits = 0
    overall_total_val = 0.0
    overall_total_cities = 0

    for st_code, st_info in raw_data.items():
        city_items: List[CityHierarchyItem] = []
        st_permits = 0
        st_val = 0.0
        st_has_parcels = False
        st_has_storms = False

        for ct_name, ct_info in st_info["cities"].items():
            if ct_info["permits"] < min_p:
                continue

            has_parcels, parcel_src = _evaluate_parcel_coverage(st_code, ct_name)
            has_storms, storm_info = _evaluate_storm_coverage(st_code, ct_name)

            if has_parcels:
                st_has_parcels = True
            if has_storms:
                st_has_storms = True

            top_contractors = [
                {"name": name, "permits": count}
                for name, count in ct_info["contractors"].most_common(5)
            ]

            jur_id = f"{st_code}-{ct_name.upper().replace(' ', '_')}"
            meta = CITY_METADATA_CATALOG.get(jur_id, {})
            if not meta and st_code == "MD":
                meta = {
                    "portal_url": "https://data.montgomerycountymd.gov/Community-Recreation/Commercial-Permits/i82y-u238",
                    "cad_portal_url": "https://sdat.dat.maryland.gov/RealProperty",
                    "metro_area": "Washington-Arlington-Alexandria Metro",
                    "lat": 39.0840,
                    "lng": -77.1528,
                }

            city_lat = ct_info["lat"] or meta.get("lat")
            city_lng = ct_info["lng"] or meta.get("lng")

            city_item = CityHierarchyItem(
                city=ct_name,
                state=st_code,
                permit_count=ct_info["permits"],
                total_valuation_usd=round(ct_info["valuation"], 2),
                roof_categories=dict(ct_info["categories"]),
                top_contractors=top_contractors,
                parcel_coverage=has_parcels,
                parcel_source=parcel_src,
                has_active_storms=has_storms,
                storm_details=storm_info,
                portal_url=meta.get("portal_url"),
                cad_portal_url=meta.get("cad_portal_url"),
                metro_area=meta.get("metro_area"),
                latitude=city_lat,
                longitude=city_lng,
            )
            city_items.append(city_item)
            st_permits += ct_info["permits"]
            st_val += ct_info["valuation"]

        # Sort cities by permit count descending
        city_items.sort(key=lambda c: c.permit_count, reverse=True)

        if city_items:
            state_item = StateHierarchyItem(
                state_code=st_code,
                state_name=US_STATE_NAMES.get(st_code, st_code),
                total_permits=st_permits,
                total_valuation_usd=round(st_val, 2),
                city_count=len(city_items),
                has_parcel_coverage=st_has_parcels,
                has_active_storms=st_has_storms,
                cities=city_items,
            )
            state_items.append(state_item)
            overall_total_permits += st_permits
            overall_total_val += st_val
            overall_total_cities += len(city_items)

    # Sort states by total permit count descending
    state_items.sort(key=lambda s: s.total_permits, reverse=True)

    return LocationHierarchyResponse(
        total_states=len(state_items),
        total_cities=overall_total_cities,
        total_permits=overall_total_permits,
        total_valuation_usd=round(overall_total_val, 2),
        states=state_items,
    )


@router.get("/states", response_model=List[StateSummaryItem])
async def list_available_states() -> List[StateSummaryItem]:
    """
    Returns a high-level summary of all states currently loaded in the warehouse with key metrics.
    """
    raw_data = _build_location_data()
    states_summary: List[StateSummaryItem] = []

    for st_code, st_info in raw_data.items():
        st_permits = sum(c["permits"] for c in st_info["cities"].values())
        st_val = sum(c["valuation"] for c in st_info["cities"].values())
        city_count = len(st_info["cities"])

        has_parcels = any(_evaluate_parcel_coverage(st_code, ct)[0] for ct in st_info["cities"].keys())
        has_storms = any(_evaluate_storm_coverage(st_code, ct)[0] for ct in st_info["cities"].keys())

        states_summary.append(StateSummaryItem(
            state_code=st_code,
            state_name=US_STATE_NAMES.get(st_code, st_code),
            total_permits=st_permits,
            total_valuation_usd=round(st_val, 2),
            city_count=city_count,
            has_parcel_coverage=has_parcels,
            has_active_storms=has_storms,
        ))

    states_summary.sort(key=lambda s: s.total_permits, reverse=True)
    return states_summary


@router.get("/cities", response_model=List[CityHierarchyItem])
async def list_available_cities(
    state: Optional[str] = Query(None, description="Filter cities by state code (e.g. TX)")
) -> List[CityHierarchyItem]:
    """
    Returns a flat list of cities with full metadata, optionally filtered by state.
    """
    hierarchy = await get_location_hierarchy(state=state, min_permits=1)
    all_cities = []
    for s in hierarchy.states:
        all_cities.extend(s.cities)
    all_cities.sort(key=lambda c: c.permit_count, reverse=True)
    return all_cities
