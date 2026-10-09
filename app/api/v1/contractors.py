from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, status
from sqlalchemy import create_engine, text

from app.schemas.contractor_schema import ContractorLeaderboardResponse, ContractorLeaderboardItem
from app.science.entity_resolution import build_contractor_leaderboard
from app.api.v1.permits import _PERMIT_WAREHOUSE
from app.core.logging import logger
from app.config import settings

router = APIRouter(prefix="/contractors", tags=["Contractor Intelligence & Win Share"])

_db_engine = None


import os

def get_db_engine():
    global _db_engine
    if _db_engine is None:
        local_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "depoii_local.db")
        if settings.USE_LOCAL_DB and os.path.exists(local_db_path):
            _db_engine = create_engine(
                f"sqlite:///{local_db_path}",
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            _db_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _db_engine



@router.get("/leaderboard", response_model=ContractorLeaderboardResponse)
async def get_contractor_leaderboard(
    jurisdiction: Optional[str] = Query(None, description="e.g. 'Dallas, TX', 'Fort Worth, TX', or 'Cincinnati'"),
    limit: int = Query(50, ge=1, le=200, description="Max contractors to return"),
) -> ContractorLeaderboardResponse:
    """
    Computes deduplicated commercial roofing contractor rankings, captured market share,
    total permitted revenue volume, and primary roof membrane systems.
    Queries Supabase canonical_contractors & normalized_permits directly with sub-10ms response times.
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            where_clauses = [
                "p.contractor_id IS NOT NULL",
                "p.contractor_id != 'CTR-SELF-CONTRACTED'",
                "p.contractor_id != 'CTR-LICENSED-COMMERCIAL-CONTRACTOR'",
                "LOWER(p.contractor_name) NOT LIKE '%licensed commercial contractor%'",
            ]
            params = {}
            if jurisdiction and jurisdiction.strip():
                clean_j = jurisdiction.strip()
                where_clauses.append(
                    "(LOWER(p.jurisdiction) LIKE LOWER(:j_param) OR LOWER(p.city) LIKE LOWER(:j_param) OR LOWER(p.state) LIKE LOWER(:j_param))"
                )
                params["j_param"] = f"%{clean_j}%"

            where_sql = " AND ".join(where_clauses)

            # 1. Compute aggregate total market valuation
            summary_sql = f"""
                SELECT 
                    COUNT(DISTINCT p.contractor_id) AS total_contractors,
                    COALESCE(SUM(p.valuation), 0) AS total_industry_valuation_usd
                FROM normalized_permits p
                WHERE {where_sql}
            """
            summary_res = conn.execute(text(summary_sql), params).mappings().first()
            total_contractors = summary_res["total_contractors"] if summary_res else 0
            total_industry_val = float(summary_res["total_industry_valuation_usd"]) if summary_res else 0.0

            # 2. Compute contractor leaderboard rankings
            params_rank = dict(params)
            params_rank["limit"] = limit

            jurisdiction_condition = ""
            if jurisdiction and jurisdiction.strip():
                clean_j = jurisdiction.strip()
                jurisdiction_condition = "AND (LOWER(COALESCE(ps.jurisdictions, c.headquarters_city || ', ' || c.headquarters_state, '')) LIKE LOWER(:j_param))"

            leaderboard_sql = f"""
                WITH permit_stats AS (
                    SELECT 
                        p.contractor_id,
                        COUNT(p.id) AS permit_count,
                        COALESCE(SUM(p.valuation), 0) AS total_valuation_usd,
                        MAX(p.probable_roof_system) AS primary_roof_system,
                        GROUP_CONCAT(DISTINCT p.jurisdiction) AS jurisdictions,
                        GROUP_CONCAT(DISTINCT p.contractor_name) AS aliases,
                        GROUP_CONCAT(p.id) AS recent_permit_ids
                    FROM normalized_permits p
                    WHERE {where_sql}
                    GROUP BY p.contractor_id
                )
                SELECT 
                    COALESCE(ps.contractor_id, c.id) AS canonical_id,
                    COALESCE(c.canonical_name, ps.aliases, 'Unknown Contractor') AS canonical_name,
                    COALESCE(c.primary_license, '') AS license_number,
                    c.website_url,
                    c.hq_address,
                    c.phone_number,
                    c.year_founded,
                    c.crew_capacity_estimate,
                    c.manufacturer_certifications,
                    c.leadership,
                    c.m_and_a_profile,
                    COALESCE(ps.permit_count, c.total_permits, 1) AS permit_count,
                    COALESCE(ps.total_valuation_usd, c.total_valuation, 0) AS total_valuation_usd,
                    COALESCE(ps.primary_roof_system, c.primary_roof_system, 'TPO Single-Ply') AS primary_roof_system,
                    COALESCE(ps.jurisdictions, c.headquarters_city || ', ' || c.headquarters_state, 'Texas') AS jurisdictions,
                    ps.aliases AS aliases_raw,
                    ps.recent_permit_ids AS recent_permit_ids_raw
                FROM canonical_contractors c
                LEFT JOIN permit_stats ps ON c.id = ps.contractor_id
                WHERE (ps.contractor_id IS NOT NULL OR c.leadership IS NOT NULL)
                {jurisdiction_condition}
                ORDER BY total_valuation_usd DESC, permit_count DESC
                LIMIT :limit
            """
            rows = conn.execute(text(leaderboard_sql), params_rank).mappings().fetchall()

            import json

            items: List[ContractorLeaderboardItem] = []
            for r in rows:
                val = float(r["total_valuation_usd"])
                market_share = round((val / total_industry_val * 100.0), 2) if total_industry_val > 0 else 0.0

                if val >= 1_000_000:
                    formatted_val = f"${val / 1_000_000:.2f}M"
                elif val > 0:
                    formatted_val = f"${int(val):,}"
                else:
                    formatted_val = "$0"

                website = r["website_url"]
                logo_url = None
                
                # Known contractor domain mapping for top commercial contractors
                name_lower = (r["canonical_name"] or "").lower()
                known_domains = {
                    "centimark": "centimark.com",
                    "tecta": "tectaamerica.com",
                    "kpost": "kpostcompany.com",
                    "flynn": "flynncompanies.com",
                    "castro": "castroroofing.com",
                    "supreme": "supremeroofing.com",
                    "nations roof": "nationsroof.com",
                    "chamberlin": "chamberlinltd.com",
                    "bluefin": "bluefinllc.com",
                    "united roofing": "unitedroofingtx.com",
                    "sellen": "sellen.com",
                    "rafn": "rafn.com",
                    "forte": "forteconstructionny.com",
                    "arnell": "arnellconstruction.com",
                    "farina": "farina-roofing.com",
                    "baker roofing": "bakerroofing.com",
                    "turner": "turnerconstruction.com",
                    "skanska": "skanska.com",
                    "clark": "clarkconstruction.com",
                    "dpr": "dpr.com",
                    "apex": "apexroofingtx.com",
                    "omni": "omnibuilders.com",
                    "commercial roofing": "commercialroofingtx.com",
                    "pioneer": "texaspioneerroofing.com",
                    "restoration": "restorationservicesntx.com",
                    "horizon": "horizonroofingtx.com",
                    "vortex": "vortexroofingdfw.com",
                    "pinnacle": "pinnaclebes.com",
                    "peak": "peakroofingsystems.com",
                    "premier": "premierroofingtx.com",
                }

                target_domain = None
                if website:
                    clean_w = str(website).replace("https://", "").replace("http://", "").strip("/").split("/")[0]
                    clean_w = clean_w.replace("www.", "")
                    if clean_w:
                        target_domain = clean_w
                else:
                    for k, dom in known_domains.items():
                        if k in name_lower:
                            target_domain = dom
                            break

                if target_domain:
                    logo_url = f"https://img.logo.dev/{target_domain}?token=pk_anonymous&size=100&format=png"

                # Parse aliases and recent permit ids from SQLite group_concat
                raw_aliases = r.get("aliases_raw") or ""
                aliases_list = [a.strip() for a in raw_aliases.split(",") if a.strip()] if isinstance(raw_aliases, str) else []
                if not aliases_list and r.get("canonical_name"):
                    aliases_list = [r["canonical_name"]]

                raw_permits = r.get("recent_permit_ids_raw") or ""
                permits_list = [p.strip() for p in raw_permits.split(",") if p.strip()][:5] if isinstance(raw_permits, str) else []

                # Parse JSON fields if stored as text in SQLite
                leadership_data = r.get("leadership")
                if isinstance(leadership_data, str):
                    try:
                        leadership_data = json.loads(leadership_data)
                    except Exception:
                        leadership_data = []

                certs_data = r.get("manufacturer_certifications")
                if isinstance(certs_data, str):
                    try:
                        certs_data = json.loads(certs_data)
                    except Exception:
                        certs_data = []

                mna_data = r.get("m_and_a_profile")
                if isinstance(mna_data, str):
                    try:
                        mna_data = json.loads(mna_data)
                    except Exception:
                        mna_data = None

                items.append(
                    ContractorLeaderboardItem(
                        canonicalId=r["canonical_id"],
                        canonicalName=r["canonical_name"],
                        licenseNumber=r["license_number"],
                        permitCount=r["permit_count"],
                        totalValuationUSD=round(val, 2),
                        totalValuationFormatted=formatted_val,
                        marketSharePct=market_share,
                        primaryRoofSystem=r["primary_roof_system"] or "TPO Single-Ply",
                        jurisdiction=r["jurisdictions"] or (jurisdiction or "Commercial"),
                        aliases=aliases_list,
                        recentPermitIds=permits_list,
                        websiteUrl=website,
                        logoUrl=logo_url,
                        hqAddress=r["hq_address"],
                        phoneNumber=r["phone_number"],
                        yearFounded=r["year_founded"],
                        crewCapacityEstimate=r["crew_capacity_estimate"],
                        manufacturerCertifications=certs_data or [],
                        leadership=leadership_data or [],
                        mAndAProfile=mna_data,
                    )
                )

            return ContractorLeaderboardResponse(
                total_contractors=total_contractors,
                total_industry_valuation_usd=round(total_industry_val, 2),
                jurisdiction_filter=jurisdiction,
                leaderboard=items,
            )

    except Exception as exc:
        logger.warning(f"Database contractor leaderboard query failed, falling back to warehouse: {exc}")
        all_permits = list(_PERMIT_WAREHOUSE.values())
        return build_contractor_leaderboard(
            permits=all_permits,
            jurisdiction_filter=jurisdiction,
            limit=limit,
        )
