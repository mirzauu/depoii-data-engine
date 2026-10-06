import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from rapidfuzz import fuzz
from app.schemas.contractor_schema import ContractorLeaderboardItem, ContractorLeaderboardResponse
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema
from app.core.logging import logger

SIMILARITY_THRESHOLD = 88.0  # RapidFuzz Token Sort Ratio threshold

# Canonical known contractors database for ground-truth bootstrapping
KNOWN_CANONICAL_CONTRACTORS: Dict[str, Dict[str, Any]] = {
    "CTR-KPOST": {
        "canonical_name": "KPost Roofing & Waterproofing",
        "primary_license": "4829",
        "headquarters_city": "Dallas",
        "headquarters_state": "TX",
        "patterns": ["kpost", "k-post", "k post"],
    },
    "CTR-EMPIRE": {
        "canonical_name": "Empire Roofing",
        "primary_license": "9940",
        "headquarters_city": "Fort Worth",
        "headquarters_state": "TX",
        "patterns": ["empire roofing", "empire commercial"],
    },
    "CTR-CENTIMARK": {
        "canonical_name": "CentiMark Corporation",
        "primary_license": "RCAT-8812",
        "headquarters_city": "Canonsburg",
        "headquarters_state": "PA",
        "patterns": ["centimark", "centi-mark"],
    },
    "CTR-BAKER": {
        "canonical_name": "Baker Roofing Company",
        "primary_license": "NC-1049",
        "headquarters_city": "Raleigh",
        "headquarters_state": "NC",
        "patterns": ["baker roofing", "baker commercial"],
    },
    "CTR-Tecta": {
        "canonical_name": "Tecta America",
        "primary_license": "IL-7721",
        "headquarters_city": "Rosemont",
        "headquarters_state": "IL",
        "patterns": ["tecta america", "tecta"],
    },
}


def clean_contractor_tokens(name: str) -> str:
    """
    Strips noise words and punctuation to isolate core brand tokens.
    e.g. 'KPOST ROOFING & WATERPROOFING INC.' -> 'kpost'
    """
    if not name:
        return ""
    s = name.lower()
    # Remove license numbers and trailing license annotations
    s = re.sub(r"[\(\[\-]\s*(?:lic(?:ense)?|tx|rcat|#)[^)\],]*[\)\]]?", "", s)
    s = re.sub(r"\blic(?:ense)?\s*[:#]?\s*[a-z0-9-]+", "", s)
    # Remove corporate designations
    s = re.sub(r"\b(inc|llc|corp|corporation|company|co|ltd|group|services)\b\.?", "", s)
    # Remove generic trade words
    s = re.sub(r"\b(roofing|waterproofing|sheet metal|commercial|contractors?)\b", "", s)
    # Remove special chars and extra spaces
    s = re.sub(r"[^a-z0-9]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def resolve_contractor_identity(
    raw_name: str,
    raw_license: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Resolves a raw municipal contractor string into a canonical ID and legal name.
    1. Checks exact license match against known registry.
    2. Checks fuzzy match against known canonical contractors.
    3. Falls back to generating a cleaned canonical identity.
    """
    if not raw_name or raw_name.strip() in ("Property Owner / Self-Contracted", "Licensed Commercial Contractor"):
        return "CTR-SELF-CONTRACTED", raw_name or "Property Owner / Self-Contracted"

    clean_name = raw_name.strip()
    norm_tokens = clean_contractor_tokens(clean_name)
    clean_lic = raw_license.strip().upper() if raw_license else None

    # 1. License match
    if clean_lic:
        for cid, info in KNOWN_CANONICAL_CONTRACTORS.items():
            if info.get("primary_license") and info["primary_license"].upper() == clean_lic:
                return cid, info["canonical_name"]

    # 2. Known patterns check
    for cid, info in KNOWN_CANONICAL_CONTRACTORS.items():
        for pat in info.get("patterns", []):
            if pat in norm_tokens or pat in clean_name.lower():
                return cid, info["canonical_name"]

        # Token sort ratio against canonical name
        ratio = fuzz.token_sort_ratio(norm_tokens, clean_contractor_tokens(info["canonical_name"]))
        if ratio >= SIMILARITY_THRESHOLD:
            return cid, info["canonical_name"]

    # 3. Dynamic Canonical ID generation
    core_token = norm_tokens.split()[0].upper() if norm_tokens else "GENERAL"
    dyn_id = f"CTR-{core_token}"
    return dyn_id, clean_name


def build_contractor_leaderboard(
    permits: List[DepoiiNormalizedPermitSchema],
    jurisdiction_filter: Optional[str] = None,
    limit: int = 50,
) -> ContractorLeaderboardResponse:
    """
    Aggregates permit filings, resolves contractor entities with RapidFuzz,
    calculates market capture revenue volume and percentage share.
    """
    filtered_permits = [
        p for p in permits
        if not jurisdiction_filter or jurisdiction_filter.lower() in p.jurisdiction.lower()
    ]

    total_industry_valuation = sum(p.valuation for p in filtered_permits)

    # Group permits by canonical contractor ID
    contractor_groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "canonical_name": "",
        "license": None,
        "total_valuation": 0.0,
        "permits": [],
        "roof_systems": defaultdict(int),
        "aliases": set(),
        "jurisdictions": set(),
    })

    for p in filtered_permits:
        cid, canonical_name = resolve_contractor_identity(p.contractor_name, p.contractor_license)
        entry = contractor_groups[cid]

        if not entry["canonical_name"] or len(canonical_name) > len(entry["canonical_name"]):
            entry["canonical_name"] = canonical_name

        if p.contractor_license and not entry["license"]:
            entry["license"] = p.contractor_license

        entry["total_valuation"] += p.valuation
        entry["permits"].append(p.id)
        entry["roof_systems"][p.probable_roof_system] += 1
        entry["aliases"].add(p.contractor_name)
        entry["jurisdictions"].add(p.jurisdiction)

    leaderboard_items: List[ContractorLeaderboardItem] = []

    for cid, data in contractor_groups.items():
        # Skip self-contracted / owner records from commercial competitor rankings
        if cid == "CTR-SELF-CONTRACTED":
            continue

        val = data["total_valuation"]
        market_share = round((val / total_industry_valuation * 100.0), 2) if total_industry_valuation > 0 else 0.0

        # Determine primary roof system by permit count
        primary_sys = max(data["roof_systems"].items(), key=lambda x: x[1])[0] if data["roof_systems"] else "TPO Single-Ply"

        # Format valuation
        if val >= 1_000_000:
            formatted_val = f"${val / 1_000_000:.2f}M"
        else:
            formatted_val = f"${int(val):,}"

        item = ContractorLeaderboardItem(
            canonicalId=cid,
            canonicalName=data["canonical_name"],
            licenseNumber=data["license"],
            permitCount=len(data["permits"]),
            totalValuationUSD=round(val, 2),
            totalValuationFormatted=formatted_val,
            marketSharePct=market_share,
            primaryRoofSystem=primary_sys,
            jurisdiction=", ".join(sorted(data["jurisdictions"])),
            aliases=sorted(list(data["aliases"])),
            recentPermitIds=data["permits"][:5],
        )
        leaderboard_items.append(item)

    # Sort descending by total captured valuation
    leaderboard_items.sort(key=lambda x: x.total_valuation_usd, reverse=True)

    return ContractorLeaderboardResponse(
        total_contractors=len(leaderboard_items),
        total_industry_valuation_usd=round(total_industry_valuation, 2),
        jurisdiction_filter=jurisdiction_filter,
        leaderboard=leaderboard_items[:limit],
    )
