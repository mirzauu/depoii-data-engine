import pytest
from app.science.nlp_membrane import (
    extract_mil_thickness,
    extract_manufacturer,
    extract_insulation,
    extract_attachment_method,
    parse_membrane_specifications,
)


def test_extract_mil_thickness():
    assert extract_mil_thickness("Tear off and install 60-mil TPO membrane") == 60
    assert extract_mil_thickness("Heavy-duty 80 mil Carlisle Sure-Weld") == 80
    assert extract_mil_thickness("45mils membrane") == 45
    assert extract_mil_thickness("General roofing without gauge") is None


def test_extract_manufacturer():
    assert extract_manufacturer("Carlisle Sure-Weld single ply") == "Carlisle SynTec"
    assert extract_manufacturer("Firestone UltraPly TPO") == "Elevate (Firestone)"
    assert extract_manufacturer("Sika Sarnafil heat welded seams") == "Sika Sarnafil"
    assert extract_manufacturer("GAF EverGuard commercial roof") == "GAF Commercial"
    assert extract_manufacturer("Johns Manville JM TPO") == "Johns Manville"
    assert extract_manufacturer("Generic unnamed membrane") is None


def test_extract_insulation():
    ins, cover, r = extract_insulation("Install 2 layers of polyiso with DensDeck cover board and R-30 rating")
    assert ins == "Polyisocyanurate (Polyiso)"
    assert cover == "Georgia-Pacific DensDeck Prime"
    assert r == "R-30"

    ins2, cover2, _ = extract_insulation("Securock over EPS insulation")
    assert ins2 == "Expanded Polystyrene (EPS)"
    assert cover2 == "USG Securock Gypsum-Fiber"


def test_extract_attachment_method():
    assert extract_attachment_method("Mechanically attached TPO system") == "Mechanically Attached"
    assert extract_attachment_method("Fully adhered FleeceBACK membrane") == "Fully Adhered"
    assert extract_attachment_method("RhinoBond induction welded plates") == "Induction Welded (RhinoBond)"
    assert extract_attachment_method("Ballasted EPDM loose laid") == "Ballasted"


def test_parse_membrane_specifications_full():
    narrative = (
        "Complete roof tear-off down to steel deck. Mechanically attach 2 layers of 2.6 inch "
        "polyiso insulation board (R-30) and 1/2 inch DensDeck Prime cover board. "
        "Install 80-mil Carlisle Sure-Weld TPO membrane fully adhered with low-VOC bonding adhesive. "
        "Provide 30-year manufacturer NDL warranty."
    )
    spec = parse_membrane_specifications(narrative)
    assert spec.probable_membrane == "TPO Single-Ply"
    assert spec.mil_thickness == 80
    assert spec.manufacturer == "Carlisle SynTec"
    assert spec.insulation_type == "Polyisocyanurate (Polyiso)"
    assert spec.cover_board == "Georgia-Pacific DensDeck Prime"
    assert spec.r_value == "R-30"
    assert spec.has_ndl_warranty_implied is True
