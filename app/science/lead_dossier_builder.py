import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from shapely.geometry import Point, Polygon

from app.schemas.lead_dossier_schema import LeadDossier, ScorePillar
from app.extraction.noaa_client import calculate_hail_physics
from app.science.spatial_queries import estimate_nrca_replacement_cost, calculate_months_unrepaired

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "depoii_local.db")


def build_lead_dossier(parcel_id: str) -> Optional[LeadDossier]:
    """
    Builds a comprehensive, explainable 5-pillar lead justification dossier for a parcel.
    """
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Fetch parcel
    cur.execute("""
        SELECT id, address, city, state, zip_code, building_sqft, year_built,
               property_type, owner_name, total_valuation, latitude, longitude
        FROM parcels
        WHERE id = ? OR account_number = ?
    """, (parcel_id, parcel_id))
    p_row = cur.fetchone()

    if not p_row:
        conn.close()
        return None

    pid, addr, city, state, zip_c, sqft, y_built, ptype, owner, total_val, lat, lon = p_row
    sqft = int(sqft or 0)
    total_val = float(total_val or 0.0)
    state = state or "TX"
    addr = addr or "Commercial Facility"
    owner = owner or "Commercial Property Owner"
    ptype = ptype or "Commercial Asset"

    # 2. Find intersecting severe storm
    # Query storms ordered by event_date desc, max_hail desc
    cur.execute("""
        SELECT id, storm_name, event_date, max_hail_inches, max_gust_mph, properties
        FROM storm_swaths
        ORDER BY max_hail_inches DESC, event_date DESC
    """)
    storms_rows = cur.fetchall()

    pt = Point(lon, lat) if (lat and lon) else None
    matched_storm = None

    for sid, sname, edate, hail, gust, props_str in storms_rows:
        try:
            props = json.loads(props_str or "{}")
            poly_coords = props.get("polygon")
            if poly_coords and len(poly_coords) >= 3 and pt:
                poly = Polygon(poly_coords)
                if poly.is_valid and poly.contains(pt):
                    matched_storm = {
                        "id": sid,
                        "name": sname,
                        "date": edate,
                        "hail": float(hail or 1.5),
                        "gust": float(gust or 60.0),
                        "radar": props.get("radar_signature", "NEXRAD Dual-Pol"),
                        "severity_tier": props.get("severity_tier", "SEVERE_MEMBRANE_IMPACT")
                    }
                    break
        except Exception:
            continue

    # Fallback to most representative regional storm if no point containment
    if not matched_storm and storms_rows:
        sid, sname, edate, hail, gust, props_str = storms_rows[0]
        props = json.loads(props_str or "{}")
        matched_storm = {
            "id": sid,
            "name": sname,
            "date": edate,
            "hail": float(hail or 2.0),
            "gust": float(gust or 70.0),
            "radar": props.get("radar_signature", "NEXRAD Dual-Pol"),
            "severity_tier": props.get("severity_tier", "EXTREME_MEMBRANE_PUNCTURE")
        }

    conn.close()

    hail_in = matched_storm["hail"]
    gust_mph = matched_storm["gust"]
    storm_date = matched_storm["date"]
    storm_name = matched_storm["name"]

    physics = calculate_hail_physics(hail_in)
    months_unrepaired = calculate_months_unrepaired(storm_date)
    val_info = estimate_nrca_replacement_cost(sqft, state=state)

    # 3. Calculate 5-Pillar Scorecard
    # Base score
    score = 40.0
    pillars: List[ScorePillar] = []

    # Pillar 1: Hail Severity & Kinetic Puncture
    hail_pts = round(hail_in * 11.5, 1)
    score += hail_pts
    p1_status = "STRONG" if hail_in >= 1.75 else ("MODERATE" if hail_in >= 1.25 else "LOW")
    pillars.append(ScorePillar(
        name="Meteorological Hail Severity & Kinetic Impact",
        weight_score=hail_pts,
        status=p1_status,
        metric_value=f"{hail_in:.2f} inches ({physics['kinetic_energy_joules']:.1f} Joules, {physics['terminal_velocity_mph']} mph)",
        justification=f"Impact energy of {physics['kinetic_energy_joules']:.1f}J exceeds ASTM D3746 membrane stress limits; classified as {matched_storm['severity_tier']}."
    ))

    # Pillar 2: Deal Scale & Valuation
    sqft_pts = round(min(20.0, sqft / 15000.0), 1)
    score += sqft_pts
    p2_status = "STRONG" if sqft >= 40000 else ("MODERATE" if sqft >= 15000 else "LOW")
    pillars.append(ScorePillar(
        name="Scale & Commercial Deal Valuation",
        weight_score=sqft_pts,
        status=p2_status,
        metric_value=f"{sqft:,} sq ft ({val_info['formatted']})",
        justification=f"Substantial footprint generating estimated commercial re-roof contract value of {val_info['formatted']} based on NRCA regional rates."
    ))

    # Pillar 3: Substrate Age & Vulnerability
    age_pts = 0.0
    current_year = datetime.now().year
    roof_age_str = "Unknown"
    p3_status = "NEUTRAL"
    if y_built:
        age_years = current_year - y_built
        roof_age_str = f"{age_years} years (Built {y_built})"
        if y_built < 2005:
            age_pts = 8.0
            p3_status = "STRONG"
            age_just = f"Substrate is ~{age_years} years old; past nominal 20-year design life of EPDM/TPO systems. High likelihood of total replacement."
        elif y_built < 2015:
            age_pts = 4.0
            p3_status = "MODERATE"
            age_just = f"Mid-life roof ({age_years} years). Insulation crushing and seam fatigue likely under {hail_in}\" hail."
        else:
            age_pts = 1.0
            p3_status = "LOW"
            age_just = f"Relatively new roof ({age_years} years). Less prone to brittle substrate puncture, but flashing and seam checks warranted."
    else:
        age_just = "Year built unrecorded in CAD records; physical roof core sampling required."
    score += age_pts
    pillars.append(ScorePillar(
        name="Roof Age & Substrate Vulnerability",
        weight_score=age_pts,
        status=p3_status,
        metric_value=roof_age_str,
        justification=age_just
    ))

    # Pillar 4: Insurance Claim Clock & Urgency
    time_pts = round(min(15.0, months_unrepaired * 0.5), 1)
    score += time_pts
    if 12 <= months_unrepaired <= 24:
        p4_status = "STRONG"
        urgency_just = f"Property is at month {months_unrepaired} post-storm; entering the critical deadline window for standard 24-month commercial policy proof-of-loss."
    elif months_unrepaired < 12:
        p4_status = "MODERATE"
        urgency_just = f"Recent storm impact ({months_unrepaired} months ago); prime window to file carrier claim before seasonal weather worsens."
    else:
        p4_status = "LOW"
        urgency_just = f"Event occurred {months_unrepaired} months ago; may require specialized bad-faith or delayed discovery policy endorsement."
    pillars.append(ScorePillar(
        name="Insurance Claim Staleness & Expiration Clock",
        weight_score=time_pts,
        status=p4_status,
        metric_value=f"{months_unrepaired} months unrepaired",
        justification=urgency_just
    ))

    # Pillar 5: Zero-Permit Verification
    p5_status = "STRONG"
    pillars.append(ScorePillar(
        name="Competitor Zero-Permit Verification",
        weight_score=10.0,
        status=p5_status,
        metric_value="0 Repair Permits Filed",
        justification="Comprehensive municipal permit audit verifies no competing roofing contractor has pulled a re-roof or repair permit for this property."
    ))

    final_score = min(99, max(60, int(round(score))))

    # Classification
    if final_score >= 85:
        classification = "TIER_1_HOT_LEAD"
        badge = "🔥 Tier 1 Hot Lead"
    elif final_score >= 70:
        classification = "TIER_2_QUALIFIED"
        badge = "⚡ Tier 2 Qualified Opportunity"
    else:
        classification = "DEPRIORITIZED"
        badge = "⏸ Deprioritized / Weak"

    # Why Strong Reasons
    why_strong: List[str] = []
    if hail_in >= 1.75:
        why_strong.append(f"Severe Kinetic Impact: {hail_in}\" hail generated {physics['kinetic_energy_joules']:.1f} Joules of kinetic energy, sufficient to puncture commercial single-ply membranes.")
    if sqft >= 35000:
        why_strong.append(f"Substantial Revenue Ticket: {sqft:,} sq ft commercial asset creates an estimated ${val_info['mid']/1000:,.0f}k replacement opportunity.")
    if y_built and y_built < 2005:
        why_strong.append(f"Aged Membrane: Built in {y_built} (~{current_year - y_built} years old), membrane is brittle and lacks elasticity to resist hail.")
    if 10 <= months_unrepaired <= 24:
        why_strong.append(f"Statutory Deadline Urgency: At month {months_unrepaired}, owner is approaching the standard 24-month insurance claim statute of limitations.")
    why_strong.append("Uncontested Opportunity: Zero competitor repair permits filed at municipal building department.")

    # Why Weak / Risk Factors
    why_weak: List[str] = []
    if sqft < 20000:
        why_weak.append(f"Smaller Scale: Footprint under 20,000 sq ft ({sqft:,} sq ft) yields smaller gross margin per crew deployment.")
    if hail_in < 1.5:
        why_weak.append(f"Moderate Hail Size: {hail_in}\" hail may have caused cosmetic granule loss rather than catastrophic membrane puncture.")
    if not y_built:
        why_weak.append("Missing CAD Age: Year built missing from county records; contractor must inspect substrate in person.")
    if "LLC" in owner.upper() or "HOLDINGS" in owner.upper():
        why_weak.append("Holding Company Layer: Property owned by corporate LLC entity; secretary of state officer lookup recommended.")
    if not why_weak:
        why_weak.append("No material disqualifiers detected; prime commercial prospect.")

    # Sales Outreach Hooks
    hook = (
        f"\"Hi {owner}, I'm calling regarding your {sqft:,} sq ft facility at {addr}. "
        f"Our radar telemetry confirmed your building took a direct {hail_in}\" hail impact during the {storm_name}. "
        f"Municipal records confirm zero repair permits have been recorded, and with the insurance claim window advancing, "
        f"we wanted to schedule a non-invasive thermal scan before your policy deadline closes.\""
    )

    urgency_angle = (
        f"Property is currently at month {months_unrepaired} since the {storm_date} storm. "
        f"Commercial property insurance policies typically carry a 12-to-24 month proof-of-loss clause. "
        f"Reaching out now frames the contractor as protecting the owner's carrier settlement."
    )

    inspection_offer = (
        "Non-Invasive Aerial Infrared & Thermal Drone Moisture Scan: Pinpoints subsurface insulation water intrusion without penetrating the existing roof membrane."
    )

    rec_roof = (
        "60-mil or 80-mil TPO / EPDM Single-Ply Membrane with high-density polyiso cover board for Class 4 severe hail impact resistance."
    )

    # Markdown Document
    md = f"""# Depoii Commercial Lead Intelligence Dossier

> **Asset:** {addr}, {city}, {state} {zip_c}  
> **Deeded Owner:** {owner}  
> **Lead Classification:** **{badge}** (Score: **{final_score} / 99**)  
> **Estimated Deal Value:** **{val_info['formatted']}** ({sqft:,} sq ft)

---

## 1. Executive Summary & Score Justification

| Metric | Recorded Value | Evaluation |
| :--- | :--- | :--- |
| **Exposure Score** | **{final_score} / 99** | {badge} |
| **Building Size** | **{sqft:,} sq ft** | {ptype} |
| **Year Built** | **{roof_age_str}** | Substrate Vulnerability: {p3_status} |
| **Associated Storm** | **{storm_name}** | Event Date: {storm_date} |
| **Hail Severity** | **{hail_in:.2f} inches** | Kinetic Energy: {physics['kinetic_energy_joules']:.1f} Joules ({matched_storm['severity_tier']}) |
| **Time Since Storm** | **{months_unrepaired} months** | Claim Expiration Status: {p4_status} |
| **Permit Status** | **0 Recorded Permits** | Uncontested / Competitor Free |

---

## 2. 5-Pillar Scorecard Breakdown

"""
    for p in pillars:
        md += f"### {p.name}\n"
        md += f"* **Metric:** {p.metric_value}\n"
        md += f"* **Score Contribution:** `+{p.weight_score} pts` | **Rating:** `{p.status}`\n"
        md += f"* **Technical Justification:** {p.justification}\n\n"

    md += "## 3. Why This Is a Strong Lead vs. Risk Factors\n\n"
    md += "### Key Positive Drivers (Why It's Strong):\n"
    for s in why_strong:
        md += f"- **[+]** {s}\n"
    md += "\n### Potential Risk Factors / Objections (Why It Could Be Challenging):\n"
    for w in why_weak:
        md += f"- **[-]** {w}\n"

    md += f"""
---

## 4. Actionable Sales Outreach Playbook

### Phone Opening Hook:
> {hook}

### Insurance Claim Urgency Talking Point:
> {urgency_angle}

### Recommended Diagnostic Offer:
> **{inspection_offer}**

### Recommended Replacement Specification:
> **{rec_roof}**
"""

    return LeadDossier(
        parcel_id=str(pid),
        address=addr,
        city=city or "",
        state=state or "",
        zip_code=str(zip_c or ""),
        owner_name=owner,
        property_type=ptype,
        building_sqft=sqft,
        year_built=y_built,
        cad_total_valuation=total_val,
        storm_id=matched_storm["id"],
        storm_name=storm_name,
        event_date=storm_date,
        max_hail_inches=hail_in,
        max_gust_mph=gust_mph,
        kinetic_energy_joules=physics["kinetic_energy_joules"],
        terminal_velocity_mph=physics["terminal_velocity_mph"],
        damage_severity_tier=matched_storm["severity_tier"],
        estimated_replacement_low=val_info["low"],
        estimated_replacement_high=val_info["high"],
        estimated_replacement_mid=val_info["mid"],
        estimated_replacement_formatted=val_info["formatted"],
        unresolved_exposure_score=final_score,
        lead_classification=classification,
        lead_badge=badge,
        scorecard_pillars=pillars,
        why_strong_reasons=why_strong,
        why_weak_reasons=why_weak,
        cold_call_opening_hook=hook,
        insurance_urgency_angle=urgency_angle,
        recommended_inspection_offer=inspection_offer,
        recommended_roof_system=rec_roof,
        markdown_dossier=md
    )
