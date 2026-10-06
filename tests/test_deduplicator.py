import pytest
from app.science.deduplicator import deduplicate_permits_in_memory, get_source_priority
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema


def make_test_permit(raw_num: str, jurisdiction: str, date: str, source: str, contractor: str) -> DepoiiNormalizedPermitSchema:
    return DepoiiNormalizedPermitSchema(
        id=f"DEP-TX-TEST-{raw_num}-{source}",
        sourceSystem=source,
        rawPermitNumber=raw_num,
        jurisdiction=jurisdiction,
        state="TX",
        issueDate=date,
        status="Issued",
        normalizedAddress="1200 Commercial Way",
        city="Dallas",
        zipCode="75201",
        valuation=500000.0,
        valuationFormatted="$500,000",
        category="Commercial Re-Roof",
        rawDescription="TPO Commercial Roof",
        probableRoofSystem="TPO Single-Ply",
        contractorName=contractor,
        isHailStormWindow=True,
        isCompetitorCapture=True,
        confidenceScore=95,
        normalizedAt="2026-10-06T12:00:00Z",
    )


def test_source_priority_hierarchy():
    # Accela should have higher priority than Socrata (lower integer value)
    assert get_source_priority("accela") < get_source_priority("socrata")
    assert get_source_priority("energov") < get_source_priority("socrata")
    assert get_source_priority("socrata") < get_source_priority("cad")


def test_deduplicate_cross_source():
    # Same permit reported by both Socrata and Accela
    socrata_permit = make_test_permit(
        raw_num="COM-2026-001",
        jurisdiction="Dallas, TX",
        date="2026-03-01",
        source="socrata",
        contractor="KPost Roofing",
    )
    accela_permit = make_test_permit(
        raw_num="COM-2026-001",
        jurisdiction="Dallas, TX",
        date="2026-03-01",
        source="accela",
        contractor="KPost Roofing & Waterproofing Inc. (Lic: 4829)",
    )
    unrelated_permit = make_test_permit(
        raw_num="COM-2026-002",
        jurisdiction="Dallas, TX",
        date="2026-03-02",
        source="socrata",
        contractor="Empire Roofing",
    )

    deduped, dup_count = deduplicate_permits_in_memory([socrata_permit, accela_permit, unrelated_permit])

    assert dup_count == 1
    assert len(deduped) == 2

    # The winner for COM-2026-001 must be the Accela version (source priority 1 over 3)
    winner = next(p for p in deduped if p.raw_permit_number == "COM-2026-001")
    assert winner.source_system == "accela"
    assert "Lic: 4829" in winner.contractor_name
