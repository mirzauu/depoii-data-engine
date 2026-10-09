"""
Calculates the exact number of Unresolved Exposure Locations in depoii_local.db.
Criteria:
1. Parcel in `parcels` has valid lat/long.
2. Parcel coordinates fall inside at least one severe storm swath (hail >= 1.0 in or wind >= 60 mph).
3. The parcel does NOT have a roofing permit issued on or after the storm event date.
"""

import os
import json
import sqlite3
from datetime import datetime
from shapely.geometry import Point, Polygon

DB_PATH = os.path.join(os.path.dirname(__file__), "depoii_local.db")

def calculate_unresolved_locations():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Load all storm swaths with valid polygons
    cur.execute("SELECT id, storm_name, event_date, max_hail_inches, properties FROM storm_swaths ORDER BY event_date DESC")
    storms_raw = cur.fetchall()

    storms = []
    for sid, sname, edate, hail, props_str in storms_raw:
        try:
            props = json.loads(props_str or "{}")
            poly_coords = props.get("polygon")
            if poly_coords and len(poly_coords) >= 3:
                poly = Polygon(poly_coords)
                if poly.is_valid and not poly.is_empty:
                    storms.append({
                        "id": sid,
                        "name": sname,
                        "event_date": edate,
                        "hail": hail or 1.0,
                        "poly": poly,
                        "bbox": poly.bounds
                    })
        except Exception:
            pass

    print(f"Loaded {len(storms)} valid storm polygons.")

    # 2. Load all parcels
    cur.execute("""
        SELECT id, address, city, state, zip_code, building_sqft, property_type, owner_name, latitude, longitude
        FROM parcels
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    parcels = cur.fetchall()
    total_parcels = len(parcels)
    print(f"Loaded {total_parcels} parcels with geo-coordinates.")

    # 3. Load all permits that have parcel_id or address with issue_date
    cur.execute("""
        SELECT parcel_id, normalized_address, issue_date
        FROM normalized_permits
        WHERE issue_date IS NOT NULL
    """)
    permit_rows = cur.fetchall()

    # Index permits by parcel_id and normalized_address -> list of issue_dates
    permits_by_parcel = {}
    permits_by_addr = {}
    for pid, addr, idate in permit_rows:
        if pid:
            p_clean = pid.strip().upper()
            if p_clean not in permits_by_parcel:
                permits_by_parcel[p_clean] = []
            permits_by_parcel[p_clean].append(idate[:10])
        if addr:
            a_clean = addr.strip().upper()
            if a_clean not in permits_by_addr:
                permits_by_addr[a_clean] = []
            permits_by_addr[a_clean].append(idate[:10])

    print(f"Loaded permits indexing {len(permits_by_parcel)} distinct parcels and {len(permits_by_addr)} addresses.")

    # 4. Check each parcel
    storm_hit_parcels = set()
    unresolved_parcels = set()
    repaired_parcels = set()
    unresolved_by_metro = {}

    for parcel_row in parcels:
        prc_id, addr, city, state, zip_c, sqft, ptype, owner, lat, lon = parcel_row
        pt = Point(lon, lat)
        prc_id_clean = (prc_id or "").strip().upper()
        addr_clean = (addr or "").strip().upper()

        hit_by_storms = []
        for s in storms:
            minx, miny, maxx, maxy = s["bbox"]
            if minx <= lon <= maxx and miny <= lat <= maxy:
                if s["poly"].contains(pt):
                    hit_by_storms.append(s)

        if not hit_by_storms:
            continue

        storm_hit_parcels.add(prc_id)

        # Check if any permit was issued on or after the earliest storm hit
        # Get all permit dates for this parcel
        p_dates = permits_by_parcel.get(prc_id_clean, []) + permits_by_addr.get(addr_clean, [])

        is_unresolved = True
        for st in hit_by_storms:
            s_date = st["event_date"]
            # Check if there is a permit issued on or after s_date
            for pd in p_dates:
                if pd >= s_date:
                    is_unresolved = False
                    break
            if not is_unresolved:
                break

        if is_unresolved:
            unresolved_parcels.add(prc_id)
            metro = f"{city}, {state}".strip(", ")
            unresolved_by_metro[metro] = unresolved_by_metro.get(metro, 0) + 1
        else:
            repaired_parcels.add(prc_id)

    print("\n" + "="*70)
    print(" UNRESOLVED EXPOSURE PARCEL AUDIT")
    print("="*70)
    print(f"Total Geocoded Parcels Evaluated: {total_parcels}")
    print(f"Parcels Physically Inside Severe Storm Footprint: {len(storm_hit_parcels)}")
    print(f"Parcels Already Captured / Permitted: {len(repaired_parcels)}")
    print(f"[*] UNRESOLVED EXPOSURE TARGETS (No Permit Filed): {len(unresolved_parcels)}")
    print("="*70)
    print("Breakdown by Metro:")
    for m, c in sorted(unresolved_by_metro.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {m}: {c} unresolved properties")

    # Financial and scale analytics on unresolved parcels
    cur.execute(f"""
        SELECT sum(building_sqft), avg(building_sqft), sum(total_valuation)
        FROM parcels
        WHERE id IN ({','.join(['?']*len(unresolved_parcels))})
    """, list(unresolved_parcels))
    tot_sqft, avg_sqft, tot_val = cur.fetchone()

    # NRCA Replacement Value estimate ($10/sqft average)
    est_roof_val = (tot_sqft or 0) * 10.0

    print("\n" + "="*70)
    print(" FINANCIAL PIPELINE & SCALE OF UNRESOLVED TARGETS")
    print("="*70)
    print(f"Total Building Footprint: {int(tot_sqft or 0):,} sq ft")
    print(f"Average Building Size: {int(avg_sqft or 0):,} sq ft")
    print(f"Total CAD Property Value: ${float(tot_val or 0):,.2f}")
    print(f"Estimated Re-Roof Pipeline Value (NRCA $10/sqft): ${est_roof_val:,.2f}")

    # Sample top 3 unresolved targets
    cur.execute(f"""
        SELECT address, city, state, building_sqft, owner_name, total_valuation
        FROM parcels
        WHERE id IN ({','.join(['?']*len(unresolved_parcels))}) AND building_sqft > 0
        ORDER BY building_sqft DESC
        LIMIT 3
    """, list(unresolved_parcels))
    samples = cur.fetchall()
    print("\nTop Sample Unresolved Commercial Targets:")
    for a, ci, st, sq, ow, val in samples:
        print(f"  • {ow} | {a}, {ci}, {st} | {int(sq):,} sq ft | Val: ${float(val or 0):,.0f} | Est. Roof: ${(sq*10):,.0f}")

    conn.close()

if __name__ == "__main__":
    calculate_unresolved_locations()
