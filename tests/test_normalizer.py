import pytest
from app.science.normalizer import (
    clean_dollar_valuation,
    format_dollar_valuation,
    clean_iso_date,
    clean_street_address,
    extract_zip_code,
    clean_contractor_info,
    infer_roof_system,
    categorize_roof_permit,
    extract_square_footage,
    normalize_socrata_permit,
    batch_normalize_permits,
)


def test_clean_dollar_valuation():
    assert clean_dollar_valuation("$1,850,000.00") == 1850000.0
    assert clean_dollar_valuation("450000") == 450000.0
    assert clean_dollar_valuation(" $ 2,500.50 ") == 2500.50
    assert clean_dollar_valuation(None) == 0.0
    assert clean_dollar_valuation(-100) == 0.0
    assert clean_dollar_valuation("invalid") == 0.0


def test_format_dollar_valuation():
    assert format_dollar_valuation(1850000) == "$1.85M"
    assert format_dollar_valuation(2000000) == "$2M"
    assert format_dollar_valuation(480000) == "$480,000"
    assert format_dollar_valuation(0) == "$0"


def test_clean_iso_date():
    assert clean_iso_date("2024-05-28T00:00:00.000") == "2024-05-28"
    assert clean_iso_date("05/28/2024") == "2024-05-28"
    assert clean_iso_date("2024-05-28") == "2024-05-28"


def test_clean_street_address():
    assert clean_street_address("1200 N STEMMONS FWY") == "1200 N Stemmons Fwy"
    assert clean_street_address("4500  AIRPORT   BLVD , , ") == "4500 Airport Blvd"
    assert clean_street_address("") == "Unspecified Address"


def test_extract_zip_code():
    assert extract_zip_code("Dallas, TX 75207-1234") == "75207"
    assert extract_zip_code("No zip here", fallback="75001") == "75001"


def test_clean_contractor_info():
    name, lic = clean_contractor_info("KPOST ROOFING (TX #4829)")
    assert name == "Kpost Roofing"
    assert lic == "4829"

    name2, lic2 = clean_contractor_info("EMPIRE ROOFING - LIC: 9940")
    assert name2 == "Empire Roofing"
    assert lic2 == "9940"

    name3, _ = clean_contractor_info("OWNER BUILDER")
    assert name3 == "Property Owner / Self-Contracted"


def test_infer_roof_system():
    assert infer_roof_system("Install 60-mil Carlisle TPO single-ply system") == "TPO Single-Ply"
    assert infer_roof_system("Replace with Firestone EPDM rubber membrane") == "EPDM Membrane"
    assert infer_roof_system("Sika Sarnafil PVC heat welded roof") == "PVC Single-Ply"
    assert infer_roof_system("4-ply built-up asphalt tar and gravel mod bit") == "Modified Bitumen / BUR"
    assert infer_roof_system("Standing seam 24 gauge architectural metal") == "Metal Standing Seam"
    assert infer_roof_system("Apply elastomeric silicone fluid coating") == "Elastomeric Restoration / Coating"
    assert infer_roof_system("General commercial maintenance") == "Unspecified Commercial System"


def test_categorize_roof_permit():
    assert categorize_roof_permit("Tear-off existing flat roof to metal deck") == "Roof Tear-Off & Replace"
    assert categorize_roof_permit("Re-roof existing commercial warehouse") == "Commercial Re-Roof"
    assert categorize_roof_permit("Silicone coating restoration") == "Commercial Waterproofing & Coating"
    assert categorize_roof_permit("Repair flashing leak on roof") == "Roof Repair & Alteration"
    assert categorize_roof_permit("New construction logistics facility") == "New Construction Commercial Roofing"


def test_extract_square_footage():
    assert extract_square_footage("Tear off 640,000 sq ft industrial warehouse") == 640000
    assert extract_square_footage("No square footage listed") is None


def test_normalize_socrata_permit():
    raw = {
        "permit_number": "2601141002",
        "issued_date": "2026-02-18",
        "street_address": "1200 N STEMMONS FWY",
        "contractor_name": "KPOST COMPANY",
        "estimated_cost": "1850000",
        "work_description": "REPLACE EXISTING ROOF SYSTEM WITH 60-MIL TPO MEMBRANE",
        "status": "Issued",
        "latitude": "32.7932",
        "longitude": "-96.8184",
    }

    norm = normalize_socrata_permit(raw, jurisdiction="Dallas, TX", state="TX")
    assert norm.id == "DEP-TX-DAL-2601141002"
    assert norm.source_system == "socrata"
    assert norm.raw_permit_number == "2601141002"
    assert norm.jurisdiction == "Dallas, TX"
    assert norm.valuation == 1850000.0
    assert norm.valuation_formatted == "$1.85M"
    assert norm.probable_roof_system == "TPO Single-Ply"
    assert norm.latitude == 32.7932
    assert norm.longitude == -96.8184
    assert norm.is_competitor_capture is True


def test_batch_normalize_permits():
    raw_list = [
        {
            "permit_number": "P-001",
            "issued_date": "2026-01-15",
            "street_address": "100 MAIN ST",
            "estimated_cost": "250000",
            "work_description": "TPO roof replacement",
        },
        {
            "permit_number": "P-002",
            "issued_date": "2026-01-20",
            "street_address": "200 ELM ST",
            "estimated_cost": "750000",
            "work_description": "EPDM membrane tear-off",
        },
    ]

    res = batch_normalize_permits(raw_list, source="socrata", jurisdiction="Dallas, TX")
    assert res.total_processed == 2
    assert res.total_normalized == 2
    assert res.total_skipped == 0
    assert res.total_valuation_usd == 1000000.0
    assert len(res.records) == 2
