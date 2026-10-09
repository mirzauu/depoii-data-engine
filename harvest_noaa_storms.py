"""
NOAA / IEM Multi-Year Severe Storm Swath Harvester (2023-2026)
---------------------------------------------------------------
Harvests ground-truth severe convective hail (>= 1.00 in) and damaging wind (>= 60 mph)
from NOAA Local Storm Reports (LSR) via the Iowa Environmental Mesonet (IEM) GeoJSON API.
Computes kinetic energy physics and generates GeoJSON swath polygon footprints.
Upserts canonical storm swaths into depoii_local.db.
"""

import os
import sys
import math
import json
import sqlite3
import httpx
from datetime import datetime, timezone
from shapely.geometry import MultiPoint, Point

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

DB_PATH = os.path.join(os.path.dirname(__file__), "depoii_local.db")
IEM_LSR_URL = "https://mesonet.agron.iastate.edu/geojson/lsr.geojson"

DENSITY_ICE_KG_M3 = 917.0  # kg/m^3

WFO_CONFIGS = {
    "FWD": {
        "metro": "Dallas-Fort Worth",
        "code": "DFW",
        "jurisdiction_id": "TX-DALLAS",
        "state": "TX",
        "radar": "NEXRAD KFWS Dual-Pol MESH"
    },
    "OKX": {
        "metro": "New York City Metro",
        "code": "NYC",
        "jurisdiction_id": "NY-NEW_YORK_CITY",
        "state": "NY",
        "radar": "NEXRAD KOKX Dual-Pol MESH"
    },
    "SEW": {
        "metro": "Seattle / Puget Sound",
        "code": "SEA",
        "jurisdiction_id": "WA-SEATTLE",
        "state": "WA",
        "radar": "NEXRAD KATX Dual-Pol MESH"
    },
    "ILN": {
        "metro": "Greater Cincinnati / Ohio Valley",
        "code": "CIN",
        "jurisdiction_id": "OH-CINCINNATI",
        "state": "OH",
        "radar": "NEXRAD KILN Dual-Pol MESH"
    },
    "LOT": {
        "metro": "Chicago Metro",
        "code": "CHI",
        "jurisdiction_id": "IL-CHICAGO",
        "state": "IL",
        "radar": "NEXRAD KLOT Dual-Pol MESH"
    },
    "BOX": {
        "metro": "Boston Metro",
        "code": "BOS",
        "jurisdiction_id": "MA-BOSTON",
        "state": "MA",
        "radar": "NEXRAD KBOX Dual-Pol MESH"
    },
    "LWX": {
        "metro": "Mid-Atlantic / Montgomery County",
        "code": "MDC",
        "jurisdiction_id": "MD-MONTGOMERY_COUNTY",
        "state": "MD",
        "radar": "NEXRAD KLWX Dual-Pol MESH"
    },
    "JAX": {
        "metro": "North Florida / Gainesville",
        "code": "GNV",
        "jurisdiction_id": "FL-GAINESVILLE",
        "state": "FL",
        "radar": "NEXRAD KJAX Dual-Pol MESH"
    },
    "TBW": {
        "metro": "Tampa Bay Metro",
        "code": "TPA",
        "jurisdiction_id": "FL-TAMPA",
        "state": "FL",
        "radar": "NEXRAD KTBW Dual-Pol MESH"
    },
    "LIX": {
        "metro": "Baton Rouge / Southeast Louisiana",
        "code": "BTR",
        "jurisdiction_id": "LA-BATON_ROUGE",
        "state": "LA",
        "radar": "NEXRAD KLIX Dual-Pol MESH"
    },
    "MTR": {
        "metro": "Northern California / Sonoma County",
        "code": "SNM",
        "jurisdiction_id": "CA-SONOMA_COUNTY",
        "state": "CA",
        "radar": "NEXRAD KMUX Dual-Pol MESH"
    }
}


def calculate_hail_physics(diameter_inches: float) -> dict:
    if diameter_inches <= 0:
        return {
            "mass_grams": 0.0,
            "terminal_velocity_mph": 0.0,
            "kinetic_energy_joules": 0.0,
            "severity_tier": "LIGHT_PRECIPITATION",
            "fill_color": "#3B82F6",
            "stroke_color": "#1D4ED8"
        }
    d_m = diameter_inches * 0.0254
    d_cm = diameter_inches * 2.54
    radius_m = d_m / 2.0
    volume_m3 = (4.0 / 3.0) * math.pi * (radius_m ** 3)
    mass_kg = volume_m3 * DENSITY_ICE_KG_M3
    mass_grams = round(mass_kg * 1000.0, 1)

    v_t_mps = 14.02 * math.sqrt(d_cm)
    v_t_mph = round(v_t_mps * 2.23694, 1)
    ke_joules = round(0.5 * mass_kg * (v_t_mps ** 2), 2)

    if diameter_inches >= 2.50:
        tier = "CATASTROPHIC_MEMBRANE_DESTROYER"
        fill = "#7F1D1D"
        stroke = "#450A0A"
    elif diameter_inches >= 2.00:
        tier = "EXTREME_MEMBRANE_PUNCTURE"
        fill = "#DC2626"
        stroke = "#991B1B"
    elif diameter_inches >= 1.75:
        tier = "SEVERE_PUNCTURE_RISK"
        fill = "#EA580C"
        stroke = "#C2410C"
    elif diameter_inches >= 1.25:
        tier = "MODERATE_MEMBRANE_IMPACT"
        fill = "#F59E0B"
        stroke = "#D97706"
    else:
        tier = "GRANULE_LOSS_MEMBRANE_STRESS"
        fill = "#EAB308"
        stroke = "#CA8A04"

    return {
        "mass_grams": mass_grams,
        "terminal_velocity_mph": v_t_mph,
        "kinetic_energy_joules": ke_joules,
        "severity_tier": tier,
        "fill_color": fill,
        "stroke_color": stroke
    }


def generate_swath_polygon(points: list) -> list:
    """
    Given a list of [lon, lat] coordinates, creates a convex hull polygon with a buffer.
    Returns list of [lon, lat] coordinates forming the exterior ring.
    """
    if not points:
        return []
    if len(points) == 1:
        pt = Point(points[0][0], points[0][1])
        poly = pt.buffer(0.045).simplify(0.005)
    elif len(points) == 2:
        mp = MultiPoint([Point(p[0], p[1]) for p in points])
        poly = mp.convex_hull.buffer(0.040).simplify(0.005)
    else:
        mp = MultiPoint([Point(p[0], p[1]) for p in points])
        poly = mp.convex_hull.buffer(0.035).simplify(0.005)

    if poly.geom_type == "Polygon":
        return [[round(c[0], 5), round(c[1], 5)] for c in poly.exterior.coords]
    elif poly.geom_type == "MultiPolygon":
        # pick the largest polygon
        largest = max(poly.geoms, key=lambda g: g.area)
        return [[round(c[0], 5), round(c[1], 5)] for c in largest.exterior.coords]
    return []


def harvest_wfo(client: httpx.Client, wfo: str, cfg: dict, start_year: int = 2023, end_year: int = 2026) -> list:
    print(f"\n[HARVEST] Fetching NOAA LSR for {wfo} ({cfg['metro']}) {start_year}-{end_year}...")
    params = {
        "sts": f"{start_year}-01-01T00:00:00Z",
        "ets": f"{end_year}-10-09T23:59:59Z",
        "wfos": wfo,
        "types": "H,W"
    }
    try:
        r = client.get(IEM_LSR_URL, params=params, timeout=45)
        if r.status_code != 200:
            print(f"  [ERROR] HTTP {r.status_code} from IEM for {wfo}")
            return []
        data = r.json()
    except Exception as e:
        print(f"  [ERROR] Network error for {wfo}: {e}")
        return []

    features = data.get("features", [])
    print(f"  Found {len(features)} total severe weather reports.")

    # Group by date
    daily_groups = {}
    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue

        ttype = props.get("typetext", "")
        mag = props.get("magf") or 0.0
        valid = props.get("valid", "")
        if not valid or len(valid) < 10:
            continue
        date_str = valid[:10]

        # Filter criteria: Hail >= 1.00 inch OR Wind >= 60 mph
        is_severe_hail = (ttype == "HAIL" and mag >= 1.00)
        is_severe_wind = (ttype == "TSTM WND GST" and mag >= 60.0)

        if not (is_severe_hail or is_severe_wind):
            continue

        if date_str not in daily_groups:
            daily_groups[date_str] = {
                "hail_reports": [],
                "wind_reports": [],
                "coords": [],
                "counties": set(),
                "cities": set()
            }

        daily_groups[date_str]["coords"].append([coords[0], coords[1]])
        county = props.get("county", "").strip()
        if county:
            daily_groups[date_str]["counties"].add(county)
        city = props.get("city", "").strip()
        if city:
            daily_groups[date_str]["cities"].add(city)

        if ttype == "HAIL":
            daily_groups[date_str]["hail_reports"].append(mag)
        elif ttype == "TSTM WND GST":
            daily_groups[date_str]["wind_reports"].append(mag)

    print(f"  Aggregated into {len(daily_groups)} distinct severe storm dates.")

    storms = []
    for date_str, grp in sorted(daily_groups.items()):
        max_hail = max(grp["hail_reports"]) if grp["hail_reports"] else 0.0
        max_wind = max(grp["wind_reports"]) if grp["wind_reports"] else 0.0
        report_count = len(grp["coords"])

        # Determine storm name
        date_dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_name = date_dt.strftime("%B %d, %Y")
        
        # Determine dominant event descriptor
        if max_hail >= 2.0:
            event_type = "Severe Hail Core"
        elif max_hail >= 1.5:
            event_type = "Convective Hail Swath"
        elif max_hail >= 1.0:
            event_type = "Severe Hail Event"
        elif max_wind >= 70:
            event_type = "Severe Derecho & Wind Swath"
        else:
            event_type = "Severe Convective Corridor"

        primary_county = list(grp["counties"])[0] if grp["counties"] else cfg["metro"]
        storm_name = f"{month_name} {cfg['metro']} {event_type}"
        storm_id = f"STORM-{date_str}-{cfg['code']}"

        polygon_coords = generate_swath_polygon(grp["coords"])
        physics = calculate_hail_physics(max_hail)

        props_json = {
            "fill_color": physics["fill_color"],
            "stroke_color": physics["stroke_color"],
            "mass_grams": physics["mass_grams"],
            "terminal_velocity_mph": physics["terminal_velocity_mph"],
            "kinetic_energy_joules": physics["kinetic_energy_joules"],
            "severity_tier": physics["severity_tier"],
            "radar_signature": cfg["radar"],
            "total_reports": report_count,
            "max_wind_mph": max_wind,
            "affected_counties": list(grp["counties"]),
            "polygon": polygon_coords
        }

        storms.append({
            "id": storm_id,
            "storm_name": storm_name,
            "event_date": date_str,
            "max_hail_inches": round(max_hail, 2),
            "max_gust_mph": round(max_wind, 1),
            "jurisdiction_id": cfg["jurisdiction_id"],
            "properties": json.dumps(props_json)
        })

    return storms


def save_storms_to_db(storms: list):
    if not storms:
        return 0, 0

    import time
    for attempt in range(5):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()

            inserted = 0
            updated = 0
            for s in storms:
                cur.execute("SELECT id FROM storm_swaths WHERE id = ?", (s["id"],))
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE storm_swaths
                        SET storm_name = ?,
                            event_date = ?,
                            max_hail_inches = ?,
                            max_gust_mph = ?,
                            jurisdiction_id = ?,
                            properties = ?
                        WHERE id = ?
                    """, (s["storm_name"], s["event_date"], s["max_hail_inches"], s["max_gust_mph"], s["jurisdiction_id"], s["properties"], s["id"]))
                    updated += 1
                else:
                    cur.execute("""
                        INSERT INTO storm_swaths (
                            id, storm_name, event_date, max_hail_inches, max_gust_mph, jurisdiction_id, properties, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (s["id"], s["storm_name"], s["event_date"], s["max_hail_inches"], s["max_gust_mph"], s["jurisdiction_id"], s["properties"], now_iso))
                    inserted += 1

            conn.commit()
            conn.close()
            return inserted, updated
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                print(f"  [DB RETRY] Database locked, waiting 3s (attempt {attempt+1}/5)...")
                time.sleep(3.0)
            else:
                raise e
    return 0, 0


def main():
    print("=" * 80)
    print(" NOAA / IEM SEVERE STORM SWATH EXPANSION (2023 - 2026)")
    print("=" * 80)

    total_inserted = 0
    total_updated = 0
    total_storms_found = 0

    with httpx.Client(timeout=60.0) as client:
        for wfo, cfg in WFO_CONFIGS.items():
            storms = harvest_wfo(client, wfo, cfg, start_year=2023, end_year=2026)
            if storms:
                ins, upd = save_storms_to_db(storms)
                total_inserted += ins
                total_updated += upd
                total_storms_found += len(storms)
                print(f"  [SAVED {wfo}] Inserted: {ins}, Updated: {upd} (Cumulative DB swaths: {total_inserted + total_updated})")

    print(f"\n[COMPLETE] Total unique storm swaths processed: {total_storms_found}")
    print(f"[DATABASE] Total new swaths inserted: {total_inserted}, updated: {total_updated}")

    # Query DB count
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total_in_db = cur.execute("SELECT count(1) FROM storm_swaths").fetchone()[0]
    by_year = cur.execute("SELECT substr(event_date, 1, 4), count(1) FROM storm_swaths GROUP BY substr(event_date, 1, 4) ORDER BY 1").fetchall()
    by_jur = cur.execute("SELECT jurisdiction_id, count(1) FROM storm_swaths GROUP BY jurisdiction_id ORDER BY 2 DESC").fetchall()
    conn.close()

    print("\n" + "=" * 80)
    print(f" TOTAL STORM SWATHS IN DATABASE: {total_in_db}")
    print("=" * 80)
    print("Breakdown by Year:")
    for yr, cnt in by_year:
        print(f"  {yr}: {cnt} storms")
    print("\nBreakdown by Jurisdiction / Metro:")
    for jur, cnt in by_jur:
        print(f"  {jur}: {cnt} storms")


if __name__ == "__main__":
    main()
