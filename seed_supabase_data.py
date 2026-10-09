import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import json
import time

from app.api.v1.permits import _PERMIT_WAREHOUSE
from app.science.parcel_seed import SEED_COMMERCIAL_PARCELS

CONNECTION_STRING = "postgresql://postgres:Alimirsa%40123@db.enbebudptwexwkxocgtv.supabase.co:5432/postgres"

def seed_jurisdictions(cur):
    print("Seeding jurisdictions from warehouse cities...")
    # Extract unique state & city pairs
    city_map = {}
    for p in _PERMIT_WAREHOUSE.values():
        st = p.state.strip().upper()
        ct = p.city.strip().title()
        if (st, ct) not in city_map:
            jur_id = f"{st}-{ct.upper().replace(' ', '_')}"
            cad_src = None
            if st == "TX":
                if ct.upper() in ["FORT WORTH", "ARLINGTON", "KELLER", "MANSFIELD"]:
                    cad_src = "Tarrant Appraisal District (TAD)"
                elif ct.upper() in ["DALLAS", "CARROLLTON", "FARMERS BRANCH", "ADDISON"]:
                    cad_src = "Dallas County CAD"
            city_map[(st, ct)] = (jur_id, st, ct, cad_src)

    # Also add any cities present in seed parcels
    for sp in SEED_COMMERCIAL_PARCELS:
        st = sp.get("state", "TX").upper().strip()
        ct = sp.get("city", "Dallas").title().strip()
        if (st, ct) not in city_map:
            jur_id = f"{st}-{ct.upper().replace(' ', '_')}"
            cad_src = "Dallas County CAD" if st == "TX" else None
            city_map[(st, ct)] = (jur_id, st, ct, cad_src)

    query = """
    INSERT INTO jurisdictions (id, state_code, city_name, parcel_cad_source)
    VALUES %s
    ON CONFLICT (state_code, city_name) DO UPDATE 
    SET parcel_cad_source = EXCLUDED.parcel_cad_source;
    """
    values = [(v[0], v[1], v[2], v[3]) for v in city_map.values()]
    execute_values(cur, query, values)
    print(f"Seeded {len(values)} jurisdictions.")
    return city_map

def seed_parcels(cur, city_map):
    print("Seeding commercial parcels...")
    parcel_rows = []
    for p in SEED_COMMERCIAL_PARCELS:
        st = p.get("state", "TX").upper().strip()
        ct = p.get("city", "Dallas").title().strip()
        jur_id = f"{st}-{ct.upper().replace(' ', '_')}"
        lat = p.get("latitude")
        lng = p.get("longitude")
        geom_point_wkt = f"SRID=4326;POINT({lng} {lat})" if lat and lng else None

        parcel_rows.append((
            p["id"],
            jur_id,
            p["address"],
            st,
            ct,
            p.get("zip_code", "75201"),
            p.get("building_sqft", 0),
            p.get("year_built"),
            p.get("property_type", "Commercial Warehouse"),
            p.get("owner_name", "Commercial REIT"),
            geom_point_wkt,
        ))

    query = """
    INSERT INTO parcels (id, jurisdiction_id, address, state, city, zip_code, building_sqft, year_built, property_type, owner_name, geom_point)
    VALUES %s
    ON CONFLICT (id) DO NOTHING;
    """
    execute_values(cur, query, parcel_rows)
    print(f"Seeded {len(parcel_rows)} commercial parcels.")

def seed_permits(cur, city_map):
    print(f"Seeding {len(_PERMIT_WAREHOUSE)} permits into normalized_permits on Supabase...")
    t0 = time.time()
    permit_rows = []
    for p in _PERMIT_WAREHOUSE.values():
        st = p.state.strip().upper()
        ct = p.city.strip().title()
        jur_id = f"{st}-{ct.upper().replace(' ', '_')}"
        lat = p.latitude
        lng = p.longitude
        geom_point_wkt = f"SRID=4326;POINT({lng} {lat})" if lat and lng else None

        # Clean dates
        issue_d = p.issue_date[:10] if p.issue_date else "2024-01-01"

        permit_rows.append((
            p.id,
            p.raw_permit_number,
            jur_id,
            p.source_system,
            p.jurisdiction,
            st,
            ct,
            issue_d,
            p.status or "Active",
            p.normalized_address or "Unknown",
            p.zip_code or "00000",
            float(p.valuation or 0.0),
            p.valuation_formatted or "$0",
            p.category or "Commercial Re-Roof",
            p.probable_roof_system or "Unspecified Commercial System",
            p.raw_description or "Commercial Roofing",
            p.contractor_name or "Unknown Contractor",
            p.contractor_license,
            p.contractor_phone,
            bool(p.is_hail_storm_window),
            bool(p.is_competitor_capture),
            int(p.confidence_score or 100),
            geom_point_wkt
        ))

    query = """
    INSERT INTO normalized_permits (
        id, raw_permit_number, jurisdiction_id, source_system, jurisdiction,
        state, city, issue_date, status, normalized_address, zip_code,
        valuation, valuation_formatted, category, probable_roof_system,
        raw_description, contractor_name, contractor_license, contractor_phone,
        is_hail_storm_window, is_competitor_capture, confidence_score, geom_point
    ) VALUES %s
    ON CONFLICT (id) DO NOTHING;
    """
    # Batch execute in chunks of 2500
    batch_size = 2500
    for i in range(0, len(permit_rows), batch_size):
        chunk = permit_rows[i:i + batch_size]
        execute_values(cur, query, chunk)
        print(f"Inserted chunk {i} to {i + len(chunk)} permits...")

    print(f"Finished inserting permits in {round(time.time() - t0, 2)}s.")

def update_jurisdiction_rollups(cur):
    print("Computing and updating jurisdiction rollups (permit counts and total valuation)...")
    cur.execute("""
    UPDATE jurisdictions j
    SET 
        total_permits = sub.total_count,
        total_valuation_usd = sub.total_val
    FROM (
        SELECT jurisdiction_id, COUNT(*) as total_count, COALESCE(SUM(valuation), 0) as total_val
        FROM normalized_permits
        WHERE jurisdiction_id IS NOT NULL
        GROUP BY jurisdiction_id
    ) sub
    WHERE j.id = sub.jurisdiction_id;
    """)

def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()

    city_map = seed_jurisdictions(cur)
    conn.commit()

    seed_parcels(cur, city_map)
    conn.commit()

    seed_permits(cur, city_map)
    conn.commit()

    update_jurisdiction_rollups(cur)
    conn.commit()

    # Verify counts
    cur.execute("SELECT COUNT(*) FROM normalized_permits;")
    permit_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jurisdictions WHERE total_permits > 0;")
    active_jurisdictions = cur.fetchone()[0]
    cur.execute("SELECT SUM(total_valuation_usd) FROM jurisdictions;")
    total_val = cur.fetchone()[0]

    print("\n================ SUPABASE MIGRATION COMPLETE ================")
    print(f"Total Normalized Permits in Supabase: {permit_count:,}")
    print(f"Active Jurisdictions with Permits:    {active_jurisdictions}")
    print(f"Total Commercial Valuation in DB:     ${total_val:,.2f}")
    print("=============================================================\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
