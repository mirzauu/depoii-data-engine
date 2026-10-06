import re
from datetime import datetime, timezone
from typing import Any, Optional, Tuple, List, Dict
from app.schemas.permit_schema import (
    DepoiiNormalizedPermitSchema,
    NormalizationBatchResultSchema,
    BatchNormalizationError,
    PermitSourceSystem,
    PermitRoofCategory,
    PermitStatus,
    ProbableRoofSystem,
)


def clean_dollar_valuation(val: Any) -> float:
    """
    Sanitizes raw currency strings into clean numeric float values.
    Handles: '$3,450,000.00', '1850000', ' 450,000 ', None -> 3450000.0
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return 0.0 if val < 0 else round(float(val), 2)
    s = str(val).strip()
    clean_str = re.sub(r"[^0-9.-]", "", s)
    if not clean_str or clean_str == "-":
        return 0.0
    try:
        num = float(clean_str)
        return 0.0 if num < 0 else round(num, 2)
    except ValueError:
        return 0.0


def format_dollar_valuation(amount: float) -> str:
    """
    Formats numeric valuations into executive presentation strings.
    e.g. 3450000 -> "$3.45M", 480000 -> "$480,000"
    """
    if not amount or amount <= 0:
        return "$0"
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        formatted = f"${millions:.2f}M"
        return formatted.replace(".00M", "M")
    return f"${int(amount):,}"


def clean_iso_date(raw_date: Any) -> str:
    """
    Normalizes any timestamp or date string into ISO 8601 'YYYY-MM-DD'.
    Handles: '2024-05-28T00:00:00.000', '05/28/2024', '2024-05-28', 'May 28, 2024'
    """
    if not raw_date:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    s = str(raw_date).strip()

    # Match YYYY-MM-DD or starts with it
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"

    # Match MM/DD/YYYY
    us_match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if us_match:
        m = us_match.group(1).zfill(2)
        d = us_match.group(2).zfill(2)
        y = us_match.group(3)
        return f"{y}-{m}-{d}"

    # Try common strptime patterns
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(s.split(".")[0] if "T" in s else s, fmt.split(".")[0])
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clean_street_address(raw_address: Any) -> str:
    """
    Standardizes street addresses into clean title case with preserved road suffixes.
    """
    if not raw_address or not str(raw_address).strip():
        return "Unspecified Address"

    addr = str(raw_address).strip()
    addr = re.sub(r"\s+", " ", addr)
    addr = re.sub(r",\s*,+", ",", addr)
    addr = re.sub(r"\s+,", ",", addr)
    addr = addr.rstrip(" ,")

    # Convert ALL CAPS to Title Case
    if addr.isupper() and len(addr) > 4:
        addr = " ".join(word.capitalize() for word in addr.split())

    # Standardize common street suffix abbreviations
    replacements = {
        r"\bDr\b": "Dr",
        r"\bSt\b": "St",
        r"\bAve\b": "Ave",
        r"\bBlvd\b": "Blvd",
        r"\bRd\b": "Rd",
        r"\bHwy\b": "Hwy",
        r"\bPkwy\b": "Pkwy",
        r"\bLn\b": "Ln",
        r"\bSte\b": "Ste",
        r"\bFwy\b": "Fwy",
    }
    for pat, rep in replacements.items():
        addr = re.sub(pat, rep, addr, flags=re.IGNORECASE)

    return addr


def extract_zip_code(val: Any, fallback: str = "75001") -> str:
    """
    Extracts 5-digit US ZIP code from a string or address line.
    """
    if not val:
        return fallback
    s = str(val)
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", s)
    return match.group(1) if match else fallback


def clean_contractor_info(raw_name: Any) -> Tuple[str, Optional[str]]:
    """
    Cleans contractor firm name and extracts license numbers.
    e.g. 'KPOST ROOFING (TX #4829)' -> ('Kpost Roofing', '4829')
    """
    if not raw_name or not str(raw_name).strip():
        return "Licensed Commercial Contractor", None

    name = str(raw_name).strip()
    name = re.sub(r"\s+", " ", name)

    # Handle placeholders
    if re.match(r"^(owner|owner\s*builder|unknown|n/a|tbd|none|to\s*be\s*determined)$", name, re.IGNORECASE):
        return "Property Owner / Self-Contracted", None

    license_num = None
    # Extract license if embedded: (TX #4829), [Lic: 1944], etc.
    lic_match = re.search(r"[(\[\-]\s*(?:lic(?:ense)?|tx|fl|ca|rcat)?\s*[#:]?\s*([A-Za-z0-9-]{3,12})\s*[)\]]?$", name, re.IGNORECASE)
    if lic_match:
        license_num = re.sub(r"^[#\s]+", "", lic_match.group(1))
        name = name[:lic_match.start()].strip()

    if name.isupper() and len(name) > 4:
        name = " ".join(word.capitalize() for word in name.split())

    # Standardize company designations
    name = re.sub(r"\bInc\.?\b", "Inc.", name, flags=re.IGNORECASE)
    name = re.sub(r"\bLLC\.?\b", "LLC", name, flags=re.IGNORECASE)
    name = re.sub(r"\bCorp\.?\b", "Corp.", name, flags=re.IGNORECASE)
    name = re.sub(r"\bCo\.?\b", "Co.", name, flags=re.IGNORECASE)

    return (name if name else "Licensed Commercial Contractor"), license_num


def normalize_permit_status(status_str: Any) -> PermitStatus:
    if not status_str:
        return "Active"
    s = str(status_str).lower()
    if "issue" in s or "approved" in s:
        return "Issued"
    if "active" in s or "open" in s or "in progress" in s:
        return "Active"
    if "final" in s or "complete" in s or "closed" in s:
        return "Finaled"
    if "review" in s or "pending" in s or "submitted" in s:
        return "Under Review"
    if "expire" in s or "cancel" in s or "void" in s:
        return "Expired"
    return "Active"


def infer_roof_system(text: Any) -> ProbableRoofSystem:
    if not text:
        return "Unspecified Commercial System"
    t = str(text).lower()

    if any(k in t for k in ("tpo", "thermoplastic", "sure-weld", "ultraply")):
        return "TPO Single-Ply"
    if any(k in t for k in ("epdm", "rubber", "sure-seal")):
        return "EPDM Membrane"
    if any(k in t for k in ("pvc", "sarnafil", "vinyl")):
        return "PVC Single-Ply"
    if any(k in t for k in ("mod bit", "modified bitumen", "bur", "built-up", "built up", "tar and gravel", "coal tar", "asphalt")):
        return "Modified Bitumen / BUR"
    if any(k in t for k in ("standing seam", "metal roof", "r-panel", "corrugated")):
        return "Metal Standing Seam"
    if any(k in t for k in ("coating", "elastomeric", "silicone", "acrylic", "fluid-applied", "waterproof")):
        return "Elastomeric Restoration / Coating"
    if any(k in t for k in ("tile", "slate", "shingle")):
        return "Commercial Tile / Shingle"

    return "Unspecified Commercial System"


def categorize_roof_permit(description: Any, work_class: Any = None) -> PermitRoofCategory:
    combined = f"{description or ''} {work_class or ''}".lower()

    if any(k in combined for k in ("tear off", "tear-off", "remove and replace")):
        return "Roof Tear-Off & Replace"
    if any(k in combined for k in ("re-roof", "reroof", "recover", "overlay")):
        return "Commercial Re-Roof"
    if any(k in combined for k in ("waterproof", "coating", "elastomeric", "silicone")):
        return "Commercial Waterproofing & Coating"
    if any(k in combined for k in ("repair", "alteration", "patch")):
        return "Roof Repair & Alteration"
    if any(k in combined for k in ("new building", "new construction", "addition")):
        return "New Construction Commercial Roofing"

    return "Commercial Re-Roof"


def extract_square_footage(text: Any) -> Optional[int]:
    if not text:
        return None
    s = str(text)
    match = re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,9})\s*(?:sq\s*ft|square\s*feet|sqft|sf)\b", s, re.IGNORECASE)
    if match:
        try:
            num = int(match.group(1).replace(",", ""))
            if 500 < num < 10_000_000:
                return num
        except ValueError:
            pass
    return None


def normalize_socrata_permit(
    raw: Dict[str, Any],
    jurisdiction: str = "Dallas, TX",
    state: str = "TX",
) -> DepoiiNormalizedPermitSchema:
    """
    Normalizes a raw Socrata permit dict into a canonical DepoiiNormalizedPermitSchema.
    """
    raw_permit_num = (
        raw.get("permit_number")
        or raw.get("permit_num")
        or raw.get("permit_")
        or raw.get("permitnumber")
        or raw.get("job_doc_number")
        or raw.get("id")
        or f"SOCRATA-{abs(hash(str(raw))) % 10000000}"
    )
    raw_permit_num = str(raw_permit_num).strip()

    raw_date = (
        raw.get("issued_date")
        or raw.get("issue_date")
        or raw.get("issuance_date")
        or raw.get("applied_date")
        or raw.get("status_date")
        or raw.get("permit_issue_date")
    )
    issue_date = clean_iso_date(raw_date)

    raw_address = (
        raw.get("street_address")
        or raw.get("original_address1")
        or raw.get("address")
        or raw.get("site_address")
        or raw.get("property_address")
        or raw.get("location")
        or (f"{raw.get('street_number', '')} {raw.get('street_name', '')}".strip() if raw.get("street_number") else "Commercial Corridor")
    )
    normalized_address = clean_street_address(raw_address)
    city = raw.get("city") or jurisdiction.split(",")[0].strip()
    zip_code = extract_zip_code(raw.get("zip_code") or raw.get("zip") or raw.get("postal_code") or normalized_address)

    raw_contractor = (
        raw.get("contractor_name")
        or raw.get("contractor_trade")
        or raw.get("contractor_1_name")
        or raw.get("contractorcompanyname")
        or raw.get("contractors_business_name")
        or raw.get("applicant")
        or raw.get("contractor")
    )
    contractor_name, contractor_license = clean_contractor_info(raw_contractor)

    raw_val = (
        raw.get("estimated_cost")
        or raw.get("total_valuation")
        or raw.get("valuation")
        or raw.get("job_value")
        or raw.get("jobValue")
        or raw.get("declared_valuation")
        or raw.get("initial_cost")
        or raw.get("estprojectcost")
    )
    valuation = clean_dollar_valuation(raw_val)
    valuation_formatted = format_dollar_valuation(valuation)

    raw_description = (
        raw.get("work_description")
        or raw.get("description")
        or raw.get("job_description")
        or raw.get("project_description")
        or raw.get("scope_of_work")
        or "Commercial re-roofing and building envelope scope."
    )
    raw_description = str(raw_description).strip()

    category = categorize_roof_permit(raw_description, raw.get("work_class") or raw.get("permit_type"))
    probable_roof_system = infer_roof_system(raw_description)
    square_footage = extract_square_footage(raw_description)
    status = normalize_permit_status(raw.get("status") or raw.get("permit_status") or raw.get("current_status"))

    # Coordinates
    lat, lon = None, None
    if raw.get("latitude") and raw.get("longitude"):
        try:
            lat = float(raw["latitude"])
            lon = float(raw["longitude"])
        except (ValueError, TypeError):
            pass
    elif isinstance(raw.get("location"), dict):
        loc = raw["location"]
        if loc.get("latitude") and loc.get("longitude"):
            try:
                lat = float(loc["latitude"])
                lon = float(loc["longitude"])
            except (ValueError, TypeError):
                pass

    clean_num = re.sub(r"[^A-Za-z0-9]", "-", raw_permit_num).upper()
    state_code = state.upper()[:2]
    jur_code = jurisdiction[:3].upper()
    canonical_id = f"DEP-{state_code}-{jur_code}-{clean_num}"

    is_storm_window = issue_date >= "2024-05-28"
    confidence = min(99, max(80, int(85 + (8 if valuation > 500_000 else 0))))

    return DepoiiNormalizedPermitSchema(
        id=canonical_id,
        source_system="socrata",
        raw_permit_number=raw_permit_num,
        jurisdiction=jurisdiction,
        state=state,
        county=raw.get("county"),
        issue_date=issue_date,
        applied_date=clean_iso_date(raw.get("applied_date")) if raw.get("applied_date") else None,
        expiration_date=clean_iso_date(raw.get("expiration_date")) if raw.get("expiration_date") else None,
        status=status,
        normalized_address=normalized_address,
        city=city,
        zip_code=zip_code,
        latitude=lat,
        longitude=lon,
        parcel_id=raw.get("parcel_id") or raw.get("pin") or raw.get("bbl") or raw.get("assessors_parcel_number"),
        valuation=valuation,
        valuation_formatted=valuation_formatted,
        category=category,
        raw_description=raw_description,
        square_footage=square_footage,
        probable_roof_system=probable_roof_system,
        contractor_name=contractor_name,
        contractor_license=contractor_license or raw.get("contractor_license_ind"),
        contractor_phone=raw.get("contractor_phone"),
        is_hail_storm_window=is_storm_window,
        associated_storm_event="May 28, 2024 Dallas Severe Hail Core" if is_storm_window else None,
        is_competitor_capture=True,
        confidence_score=confidence,
        normalized_at=datetime.now(timezone.utc).isoformat(),
    )


def batch_normalize_permits(
    raw_records: List[Dict[str, Any]],
    source: PermitSourceSystem = "socrata",
    jurisdiction: str = "Dallas, TX",
    state: str = "TX",
) -> NormalizationBatchResultSchema:
    """
    Batch processes a list of raw municipal records into canonical permits.
    """
    records: List[DepoiiNormalizedPermitSchema] = []
    errors: List[BatchNormalizationError] = []
    total_val = 0.0

    for idx, raw in enumerate(raw_records):
        try:
            norm = normalize_socrata_permit(raw, jurisdiction=jurisdiction, state=state)
            records.append(norm)
            total_val += norm.valuation
        except Exception as e:
            raw_id = raw.get("permit_number") or raw.get("permit_num") or raw.get("id")
            errors.append(BatchNormalizationError(
                index=idx,
                raw_id=str(raw_id) if raw_id else None,
                error=str(e),
            ))

    return NormalizationBatchResultSchema(
        total_processed=len(raw_records),
        total_normalized=len(records),
        total_skipped=len(errors),
        total_valuation_usd=round(total_val, 2),
        jurisdiction=jurisdiction,
        source_system=source,
        records=records,
        errors=errors,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
