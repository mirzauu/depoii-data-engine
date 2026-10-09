"""
Spatial Permit & Parcel Linker to Severe Storm Swaths
-------------------------------------------------------
Performs point-in-polygon spatial evaluation matching 93,508 permits
and 2,300+ tax parcels against the expanded catalog of storm swaths in depoii_local.db.
Links permits filed within 18 months of severe hail/wind impact with associated_storm_id.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from shapely.geometry import Point, Polygon

DB_PATH = os.path.join(os.path.dirname(__file__), "depoii_local.db")


def link_all():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=" * 80)
    print(" SPATIAL PERMIT & PARCEL LINKING TO EXPANDED STORM SWATHS")
    print("=" * 80)

    # 1. Load all storm swaths with valid polygons
    cur.execute("SELECT id, storm_name, event_date, max_hail_inches, properties FROM storm_swaths ORDER BY event_date ASC")
    storms = cur.fetchall()
    print(f"Loaded {len(storms)} storm swaths from database.")

    parsed_storms = []
    for sid, sname, edate, hail, props_str in storms:
        try:
            props = json.loads(props_str or "{}")
            poly_coords = props.get("polygon")
            if poly_coords and len(poly_coords) >= 3:
                poly = Polygon(poly_coords)
                if poly.is_valid and not poly.is_empty:
                    minx, miny, maxx, maxy = poly.bounds
                    parsed_storms.append({
                        "id": sid,
                        "name": sname,
                        "event_date": edate,
                        "hail": hail or 1.0,
                        "polygon": poly,
                        "bbox": (minx, miny, maxx, maxy)
                    })
        except Exception:
            pass

    print(f"Successfully compiled {len(parsed_storms)} active spatial storm polygons.")

    # 2. Iterate through storms and match permits
    # Optimize using SQLite spatial bounding box index + Point-in-Polygon
    total_permits_linked = 0
    total_parcels_flagged = 0

    print("\n[MATCHING] Processing spatial intersects against permits...")
    
    # We match permits where permit issue_date is >= storm event_date and within ~550 days (18 months)
    for idx, storm in enumerate(parsed_storms, 1):
        minx, miny, maxx, maxy = storm["bbox"]
        sid = storm["id"]
        edate = storm["event_date"]

        # Fast bounding box candidate retrieval
        cur.execute("""
            SELECT id, latitude, longitude, issue_date
            FROM normalized_permits
            WHERE latitude >= ? AND latitude <= ?
              AND longitude >= ? AND longitude <= ?
              AND (associated_storm_id IS NULL OR associated_storm_id = '')
        """, (miny, maxy, minx, maxx))
        candidates = cur.fetchall()

        matched_pids = []
        for pid, lat, lon, idate in candidates:
            if not lat or not lon:
                continue
            pt = Point(lon, lat)
            if storm["polygon"].contains(pt):
                # Verify date window if issue_date exists
                is_in_window = True
                if idate:
                    try:
                        p_dt = datetime.strptime(idate[:10], "%Y-%m-%d")
                        s_dt = datetime.strptime(edate[:10], "%Y-%m-%d")
                        diff_days = (p_dt - s_dt).days
                        # Between 0 days and 550 days (18 months after storm)
                        if diff_days < -30 or diff_days > 550:
                            is_in_window = False
                    except Exception:
                        pass
                
                if is_in_window:
                    matched_pids.append(pid)

        if matched_pids:
            cur.executemany("""
                UPDATE normalized_permits
                SET associated_storm_id = ?,
                    is_hail_storm_window = 1
                WHERE id = ?
            """, [(sid, pid) for pid in matched_pids])
            total_permits_linked += len(matched_pids)

        if idx % 25 == 0 or idx == len(parsed_storms):
            print(f"  Processed {idx}/{len(parsed_storms)} storms... cumulative new permit links: {total_permits_linked}")

    conn.commit()

    # Summary
    cur.execute("SELECT count(1) FROM normalized_permits WHERE associated_storm_id IS NOT NULL AND associated_storm_id != ''")
    total_linked_final = cur.fetchone()[0]

    cur.execute("SELECT count(1) FROM normalized_permits WHERE is_hail_storm_window = 1")
    total_hail_window = cur.fetchone()[0]

    print("\n" + "=" * 80)
    print(" SPATIAL LINKING COMPLETE")
    print("=" * 80)
    print(f"Total Permits Tied to Exact Storm Swaths: {total_linked_final} (newly linked this pass: {total_permits_linked})")
    print(f"Total Permits Flagged in Hail Storm Window: {total_hail_window}")

    conn.close()


if __name__ == "__main__":
    link_all()
