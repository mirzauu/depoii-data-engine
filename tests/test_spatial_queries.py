import pytest
from app.science.spatial_queries import (
    estimate_nrca_replacement_cost,
    calculate_exposure_score,
    evaluate_spatial_exposure_in_memory,
    get_postgis_unresolved_exposure_sql,
)
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.extraction.noaa_client import DFW_MAY28_SWATH_POLYGON


def test_estimate_nrca_replacement_cost():
    # 100,000 sq ft warehouse in Texas
    cost = estimate_nrca_replacement_cost(100000, state="TX")
    assert cost["low"] > 0
    assert cost["high"] > cost["low"]
    assert cost["mid"] == (cost["low"] + cost["high"]) / 2
    assert "$" in cost["formatted"]


def test_calculate_exposure_score():
    score = calculate_exposure_score(
        hail_inches=2.50,
        building_sqft=200000,
        months_unrepaired=28,
        year_built=1995,
    )
    assert 60 <= score <= 99


def test_postgis_sql_template():
    sql = get_postgis_unresolved_exposure_sql()
    assert "ST_Intersects" in sql
    assert "normalized_permits" in sql
    assert ":min_sqft" in sql


def test_spatial_exposure_in_memory():
    # 1 parcel inside the polygon (12800 Stemmons Fwy is inside)
    # 1 parcel outside the polygon
    parcels = [
        {
            "id": "PARCEL-INSIDE-UNREPAIRED",
            "address": "12800 Stemmons Fwy",
            "city": "Dallas",
            "zip_code": "75234",
            "state": "TX",
            "building_sqft": 240000,
            "year_built": 1990,
            "property_type": "Cold Storage",
            "owner_name": "Lineage Logistics",
            "latitude": 32.9210,
            "longitude": -96.8940,
        },
        {
            "id": "PARCEL-INSIDE-REPAIRED",
            "address": "16650 Westgrove Dr",
            "city": "Dallas",
            "zip_code": "75248",
            "state": "TX",
            "building_sqft": 185000,
            "year_built": 1998,
            "property_type": "Flex Logistics",
            "owner_name": "Prologis",
            "latitude": 32.9774,
            "longitude": -96.8378,
        },
        {
            "id": "PARCEL-OUTSIDE",
            "address": "9999 South Austin Blvd",
            "city": "Austin",
            "zip_code": "78701",
            "state": "TX",
            "building_sqft": 150000,
            "year_built": 2000,
            "property_type": "Warehouse",
            "owner_name": "Austin Trust",
            "latitude": 30.2672,
            "longitude": -97.7431,  # Far outside DFW swath
        },
    ]

    storm_meta = {
        "storm_name": "May 28, 2024 Dallas Severe Hail Core",
        "event_date": "2024-05-28",
        "max_hail_inches": 2.50,
    }

    # Simulate that PARCEL-INSIDE-REPAIRED has a post-storm permit
    repaired_permit = DepoiiNormalizedPermitSchema(
        id="DEP-TX-DAL-001",
        sourceSystem="socrata",
        rawPermitNumber="2601141002",
        jurisdiction="Dallas, TX",
        state="TX",
        issueDate="2024-06-15",  # Issued after storm
        status="Issued",
        normalizedAddress="16650 Westgrove Dr",
        city="Dallas",
        zipCode="75248",
        parcelId="PARCEL-INSIDE-REPAIRED",
        valuation=1850000.0,
        valuationFormatted="$1.85M",
        category="Commercial Re-Roof",
        rawDescription="TPO replacement",
        probableRoofSystem="TPO Single-Ply",
        contractorName="KPost Roofing",
        isHailStormWindow=True,
        isCompetitorCapture=True,
        confidenceScore=95,
        normalizedAt="2026-10-06T12:00:00Z",
    )

    targets = evaluate_spatial_exposure_in_memory(
        parcels=parcels,
        swath_polygon_coords=DFW_MAY28_SWATH_POLYGON,
        storm_metadata=storm_meta,
        existing_permits=[repaired_permit],
        min_sqft=50000,
    )

    # PARCEL-OUTSIDE must be rejected (spatial filter)
    # PARCEL-INSIDE-REPAIRED must be rejected (already repaired)
    # Only PARCEL-INSIDE-UNREPAIRED should be in targets!
    assert len(targets) == 1
    t = targets[0]
    assert t.parcel_id == "PARCEL-INSIDE-UNREPAIRED"
    assert t.address == "12800 Stemmons Fwy"
    assert t.has_repair_permit is False
    assert t.building_sqft == 240000
    assert t.estimated_replacement_mid > 1_000_000
    assert t.lead_tier == "TIER_1_ENTERPRISE"
