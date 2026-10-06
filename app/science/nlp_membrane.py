import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class MembraneSpecDetails(BaseModel):
    probable_membrane: str
    mil_thickness: Optional[int] = None
    manufacturer: Optional[str] = None
    insulation_type: Optional[str] = None
    r_value: Optional[str] = None
    attachment_method: Optional[str] = None
    cover_board: Optional[str] = None
    has_ndl_warranty_implied: bool = False


# Known commercial roofing manufacturers and their trademarked product lines
MANUFACTURER_SIGNATURES: Dict[str, List[str]] = {
    "Carlisle SynTec": [
        "carlisle", "sure-weld", "sure-seal", "fleeceback", "syntec", "sure-flex"
    ],
    "Elevate (Firestone)": [
        "elevate", "firestone", "ultraply", "rubbergard", "holcim building envelope"
    ],
    "GAF Commercial": [
        "gaf", "everguard", "ruberoid", "gaf commercial"
    ],
    "Johns Manville": [
        "johns manville", "jm tpo", "dynaweld", "jm epdm"
    ],
    "Sika Sarnafil": [
        "sika", "sarnafil", "sikaplan", "sarnamatic"
    ],
    "Soprema": [
        "soprema", "sopralene", "elastophene"
    ],
    "Tremco": [
        "tremco", "alphaguard", "powerply"
    ],
    "Mule-Hide": [
        "mule-hide", "mule hide"
    ],
}


def extract_mil_thickness(text: str) -> Optional[int]:
    """
    Extracts mil thickness from narrative:
    e.g. 'install 60-mil TPO', '80 mil membrane', '45mils' -> 60, 80, 45
    """
    if not text:
        return None
    match = re.search(r"\b(45|50|60|72|80|90|115|120|135)\s*(?:-?\s*mils?)\b", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def extract_manufacturer(text: str) -> Optional[str]:
    """
    Identifies commercial membrane manufacturer from narrative signatures.
    """
    if not text:
        return None
    t = text.lower()
    for mfr, signatures in MANUFACTURER_SIGNATURES.items():
        if any(sig in t for sig in signatures):
            return mfr
    return None


def extract_insulation(text: str) -> Tuple_Insulation:
    """
    Extracts insulation chemistry, cover board, and R-value.
    """
    t = text.lower() if text else ""
    ins_type = None
    if "polyiso" in t or "polyisocyanurate" in t or "iso board" in t:
        ins_type = "Polyisocyanurate (Polyiso)"
    elif "eps" in t or "expanded polystyrene" in t:
        ins_type = "Expanded Polystyrene (EPS)"
    elif "xps" in t or "extruded polystyrene" in t:
        ins_type = "Extruded Polystyrene (XPS)"

    cover_board = None
    if "densdeck" in t or "dens deck" in t:
        cover_board = "Georgia-Pacific DensDeck Prime"
    elif "securock" in t:
        cover_board = "USG Securock Gypsum-Fiber"

    r_val = None
    r_match = re.search(r"\b(r-?\s*(?:15|20|25|30|35|40|50))\b", t, re.IGNORECASE)
    if r_match:
        r_val = r_match.group(1).upper().replace(" ", "")

    return ins_type, cover_board, r_val


Tuple_Insulation = tuple[Optional[str], Optional[str], Optional[str]]


def extract_attachment_method(text: str) -> Optional[str]:
    """
    Identifies fastening method: Mechanically Attached, Fully Adhered, etc.
    """
    if not text:
        return None
    t = text.lower()
    if "fully adhered" in t or "adhered system" in t or "glued down" in t:
        return "Fully Adhered"
    if "mechanically attached" in t or "mechanically fastened" in t or "screw and plate" in t:
        return "Mechanically Attached"
    if "rhinobond" in t or "induction weld" in t:
        return "Induction Welded (RhinoBond)"
    if "ballasted" in t or "ballast rock" in t:
        return "Ballasted"
    return None


def parse_membrane_specifications(narrative: str) -> MembraneSpecDetails:
    """
    Full NLP / Regex extraction pipeline analyzing unstructured municipal narratives.
    """
    from app.science.normalizer import infer_roof_system

    membrane = infer_roof_system(narrative)
    mils = extract_mil_thickness(narrative)
    mfr = extract_manufacturer(narrative)
    ins_type, cover_board, r_val = extract_insulation(narrative)
    attachment = extract_attachment_method(narrative)

    # Implied 20-30 yr NDL warranty if commercial grade 60/80-mil + polyiso + major mfr
    has_ndl = bool(mfr and mils and mils >= 60 and ins_type)

    return MembraneSpecDetails(
        probable_membrane=membrane,
        mil_thickness=mils,
        manufacturer=mfr,
        insulation_type=ins_type,
        r_value=r_val,
        attachment_method=attachment,
        cover_board=cover_board,
        has_ndl_warranty_implied=has_ndl,
    )
