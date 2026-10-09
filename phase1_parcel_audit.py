import sqlite3
import json

def run_phase1_audit():
    db_path = "d:/projects/Roofx/depoii-data-engine/depoii_local.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Total records
    cur.execute("SELECT COUNT(*) FROM normalized_permits")
    total = cur.fetchone()[0]

    # 2. Existing parcel_id
    cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE parcel_id IS NOT NULL AND length(trim(parcel_id)) > 0")
    with_parcel = cur.fetchone()[0]

    # 3. Lat / Lon availability
    cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0")
    with_lat_lon = cur.fetchone()[0]

    # 4. Valid address & zip code
    cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE normalized_address IS NOT NULL AND length(trim(normalized_address)) > 0")
    with_address = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE zip_code IS NOT NULL AND length(trim(zip_code)) > 0 AND zip_code != '00000'")
    with_zip = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM normalized_permits 
        WHERE normalized_address IS NOT NULL AND length(trim(normalized_address)) > 0 
          AND zip_code IS NOT NULL AND length(trim(zip_code)) > 0 AND zip_code != '00000'
    """)
    with_addr_and_zip = cur.fetchone()[0]

    # 5. Jurisdiction Breakdown
    cur.execute("""
        SELECT jurisdiction, 
               COUNT(*) as total, 
               SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0 THEN 1 ELSE 0 END) as has_coords,
               SUM(CASE WHEN normalized_address IS NOT NULL AND length(trim(normalized_address)) > 0 THEN 1 ELSE 0 END) as has_addr,
               SUM(CASE WHEN parcel_id IS NOT NULL AND length(trim(parcel_id)) > 0 THEN 1 ELSE 0 END) as has_parcel
        FROM normalized_permits
        GROUP BY jurisdiction
        ORDER BY total DESC
    """)
    jurisdiction_stats = cur.fetchall()

    # 6. Sample addresses across jurisdictions
    cur.execute("""
        SELECT raw_permit_number, jurisdiction, normalized_address, city, zip_code, latitude, longitude, parcel_id 
        FROM normalized_permits 
        LIMIT 6
    """)
    sample_rows = cur.fetchall()

    audit_result = {
        "total_permits": total,
        "with_parcel_id": with_parcel,
        "with_coordinates": with_lat_lon,
        "with_address": with_address,
        "with_zip": with_zip,
        "with_address_and_zip": with_addr_and_zip,
        "jurisdictions": [
            {
                "jurisdiction": r[0],
                "count": r[1],
                "has_coords": r[2],
                "has_addr": r[3],
                "has_parcel": r[4]
            }
            for r in jurisdiction_stats
        ],
        "sample_permits": [
            {
                "permit": r[0],
                "jurisdiction": r[1],
                "address": r[2],
                "city": r[3],
                "zip": r[4],
                "lat": r[5],
                "lon": r[6],
                "parcel_id": r[7]
            }
            for r in sample_rows
        ]
    }

    print(json.dumps(audit_result, indent=2))

if __name__ == "__main__":
    run_phase1_audit()
