import pytest
from app.science.entity_resolution import (
    clean_contractor_tokens,
    resolve_contractor_identity,
    build_contractor_leaderboard,
)
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema


def test_clean_contractor_tokens():
    assert clean_contractor_tokens("KPOST ROOFING & WATERPROOFING INC.") == "kpost"
    assert clean_contractor_tokens("EMPIRE ROOFING - LIC: 9940") == "empire"
    assert clean_contractor_tokens("CENTIMARK CORPORATION") == "centimark"
    assert clean_contractor_tokens("") == ""


def test_resolve_contractor_identity_by_license():
    # Matching trade license '4829'
    cid, name = resolve_contractor_identity("K-Post Commercial", raw_license="4829")
    assert cid == "CTR-KPOST"
    assert name == "KPost Roofing & Waterproofing"


def test_resolve_contractor_identity_fuzzy():
    # Fuzzy variations of KPost without license
    cid1, name1 = resolve_contractor_identity("KPOST ROOFING SERVICES LLC")
    assert cid1 == "CTR-KPOST"
    assert name1 == "KPost Roofing & Waterproofing"

    # CentiMark variation
    cid2, name2 = resolve_contractor_identity("Centi-Mark Roofing Corp")
    assert cid2 == "CTR-CENTIMARK"
    assert name2 == "CentiMark Corporation"

    # Unknown contractor dynamic resolution
    cid3, name3 = resolve_contractor_identity("Apex Sky Roofing")
    assert cid3.startswith("CTR-")
    assert "Apex Sky Roofing" in name3


def test_build_contractor_leaderboard():
    permits = [
        DepoiiNormalizedPermitSchema(
            id="P-001",
            sourceSystem="socrata",
            rawPermitNumber="2601",
            jurisdiction="Dallas, TX",
            state="TX",
            issueDate="2024-06-01",
            status="Issued",
            normalizedAddress="100 Main St",
            city="Dallas",
            zipCode="75201",
            valuation=3000000.0,
            valuationFormatted="$3M",
            category="Roof Tear-Off & Replace",
            rawDescription="TPO replacement",
            probableRoofSystem="TPO Single-Ply",
            contractorName="KPOST COMPANY",
            contractorLicense="4829",
            isHailStormWindow=True,
            isCompetitorCapture=True,
            confidenceScore=95,
            normalizedAt="2026-10-06T12:00:00Z",
        ),
        DepoiiNormalizedPermitSchema(
            id="P-002",
            sourceSystem="socrata",
            rawPermitNumber="2602",
            jurisdiction="Dallas, TX",
            state="TX",
            issueDate="2024-06-05",
            status="Issued",
            normalizedAddress="200 Elm St",
            city="Dallas",
            zipCode="75202",
            valuation=1000000.0,
            valuationFormatted="$1M",
            category="Commercial Re-Roof",
            rawDescription="PVC recovery",
            probableRoofSystem="PVC Single-Ply",
            contractorName="KPost Roofing & Waterproofing Inc.",
            contractorLicense="4829",
            isHailStormWindow=True,
            isCompetitorCapture=True,
            confidenceScore=95,
            normalizedAt="2026-10-06T12:00:00Z",
        ),
        DepoiiNormalizedPermitSchema(
            id="P-003",
            sourceSystem="accela",
            rawPermitNumber="2603",
            jurisdiction="Fort Worth, TX",
            state="TX",
            issueDate="2024-06-10",
            status="Issued",
            normalizedAddress="300 Commerce St",
            city="Fort Worth",
            zipCode="76102",
            valuation=1000000.0,
            valuationFormatted="$1M",
            category="Commercial Re-Roof",
            rawDescription="EPDM roof",
            probableRoofSystem="EPDM Membrane",
            contractorName="Empire Roofing",
            contractorLicense="9940",
            isHailStormWindow=True,
            isCompetitorCapture=True,
            confidenceScore=95,
            normalizedAt="2026-10-06T12:00:00Z",
        ),
    ]

    res = build_contractor_leaderboard(permits)
    assert res.total_contractors == 2  # KPost (2 permits grouped into 1) and Empire
    assert res.total_industry_valuation_usd == 5000000.0

    kpost = res.leaderboard[0]
    assert kpost.canonical_id == "CTR-KPOST"
    assert kpost.permit_count == 2
    assert kpost.total_valuation_usd == 4000000.0
    assert kpost.market_share_pct == 80.0
    assert len(kpost.aliases) == 2

    empire = res.leaderboard[1]
    assert empire.canonical_id == "CTR-EMPIRE"
    assert empire.market_share_pct == 20.0
