import os
import sys
import time
import sqlite3
from sqlalchemy import create_engine, text

SUPABASE_URL = "postgresql://postgres:Alimirsa%40123@db.enbebudptwexwkxocgtv.supabase.co:5432/postgres"
LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "depoii_local.db")

def main():
    print(f"[{time.strftime('%X')}] Starting local sync...", flush=True)
    if os.path.exists(LOCAL_DB_PATH):
        try:
            os.remove(LOCAL_DB_PATH)
        except Exception as e:
            print(f"Notice: {e}", flush=True)

    local_conn = sqlite3.connect(LOCAL_DB_PATH)
    local_cur = local_conn.cursor()
    local_cur.execute("PRAGMA journal_mode = WAL;")
    local_cur.execute("PRAGMA synchronous = OFF;")

    print(f"[{time.strftime('%X')}] Creating schema...", flush=True)
    local_cur.execute("""
        CREATE TABLE normalized_permits (
            id TEXT PRIMARY KEY,
            raw_permit_number TEXT,
            jurisdiction_id TEXT,
            parcel_id TEXT,
            contractor_id TEXT,
            source_system TEXT,
            jurisdiction TEXT,
            state TEXT,
            city TEXT,
            issue_date TEXT,
            applied_date TEXT,
            expiration_date TEXT,
            status TEXT,
            normalized_address TEXT,
            zip_code TEXT,
            valuation REAL,
            valuation_formatted TEXT,
            category TEXT,
            probable_roof_system TEXT,
            raw_description TEXT,
            square_footage INTEGER,
            contractor_name TEXT,
            contractor_license TEXT,
            contractor_phone TEXT,
            is_hail_storm_window INTEGER,
            associated_storm_id TEXT,
            is_competitor_capture INTEGER,
            confidence_score INTEGER,
            latitude REAL,
            longitude REAL,
            normalized_at TEXT
        );
    """)

    local_cur.execute("""
        CREATE TABLE canonical_contractors (
            id TEXT PRIMARY KEY,
            canonical_name TEXT,
            primary_license TEXT,
            headquarters_city TEXT,
            headquarters_state TEXT,
            total_permits INTEGER,
            total_valuation REAL,
            primary_roof_system TEXT,
            created_at TEXT,
            updated_at TEXT,
            website_url TEXT,
            hq_address TEXT,
            phone_number TEXT,
            year_founded INTEGER,
            crew_capacity_estimate TEXT,
            leadership TEXT,
            manufacturer_certifications TEXT,
            m_and_a_profile TEXT
        );
    """)

    local_cur.execute("""
        CREATE TABLE storm_swaths (
            id TEXT PRIMARY KEY,
            storm_name TEXT,
            event_date TEXT,
            max_hail_inches REAL,
            max_gust_mph REAL,
            jurisdiction_id TEXT,
            properties TEXT,
            created_at TEXT
        );
    """)
    local_conn.commit()

    print(f"[{time.strftime('%X')}] Connecting to Supabase...", flush=True)
    remote_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)

    # 1. Normalized permits in chunks using server-side cursor / LIMIT OFFSET
    total_permits = 21372
    chunk_size = 2500
    insert_sql = """
        INSERT INTO normalized_permits VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    with remote_engine.connect() as r_conn:
        for offset in range(0, total_permits + chunk_size, chunk_size):
            t_chunk = time.time()
            q = text(f"""
                SELECT 
                    id, raw_permit_number, jurisdiction_id, parcel_id, contractor_id,
                    source_system, jurisdiction, state, city,
                    issue_date::text, applied_date::text, expiration_date::text,
                    status, normalized_address, zip_code,
                    valuation::float, valuation_formatted, category, probable_roof_system,
                    raw_description, square_footage, contractor_name, contractor_license,
                    contractor_phone, 
                    CASE WHEN is_hail_storm_window THEN 1 ELSE 0 END,
                    associated_storm_id,
                    CASE WHEN is_competitor_capture THEN 1 ELSE 0 END,
                    confidence_score, latitude::float, longitude::float, normalized_at::text
                FROM normalized_permits
                ORDER BY id
                LIMIT {chunk_size} OFFSET {offset}
            """)
            rows = r_conn.execute(q).fetchall()
            if not rows:
                break
            local_cur.executemany(insert_sql, [tuple(r) for r in rows])
            local_conn.commit()
            print(f"[{time.strftime('%X')}] Mirrored {offset + len(rows)} / {total_permits} permits ({time.time()-t_chunk:.2f}s for chunk)", flush=True)

        # 2. Canonical contractors
        print(f"[{time.strftime('%X')}] Mirroring canonical contractors...", flush=True)
        c_q = text("""
            SELECT 
                id, canonical_name, primary_license, headquarters_city, headquarters_state,
                total_permits, total_valuation::float, primary_roof_system, created_at::text,
                updated_at::text, website_url, hq_address, phone_number, year_founded,
                crew_capacity_estimate, leadership::text, manufacturer_certifications::text,
                m_and_a_profile::text
            FROM canonical_contractors
        """)
        c_rows = r_conn.execute(c_q).fetchall()
        local_cur.executemany("INSERT INTO canonical_contractors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(r) for r in c_rows])
        local_conn.commit()
        print(f"[{time.strftime('%X')}] Mirrored {len(c_rows)} canonical contractors.", flush=True)

        # 3. Storm swaths
        print(f"[{time.strftime('%X')}] Mirroring storm swaths...", flush=True)
        s_q = text("""
            SELECT 
                id, storm_name, event_date::text, max_hail_inches::float, max_gust_mph::float,
                jurisdiction_id, properties::text, created_at::text
            FROM storm_swaths
        """)
        s_rows = r_conn.execute(s_q).fetchall()
        local_cur.executemany("INSERT INTO storm_swaths VALUES (?,?,?,?,?,?,?,?)", [tuple(r) for r in s_rows])
        local_conn.commit()
        print(f"[{time.strftime('%X')}] Mirrored {len(s_rows)} storm swaths.", flush=True)

    # 4. Indexes
    print(f"[{time.strftime('%X')}] Building btree indexes...", flush=True)
    t_idx = time.time()
    indexes = [
        "CREATE INDEX idx_np_val ON normalized_permits(valuation DESC);",
        "CREATE INDEX idx_np_jur ON normalized_permits(jurisdiction);",
        "CREATE INDEX idx_np_city ON normalized_permits(city);",
        "CREATE INDEX idx_np_status ON normalized_permits(status);",
        "CREATE INDEX idx_np_roof ON normalized_permits(probable_roof_system);",
        "CREATE INDEX idx_np_contractor ON normalized_permits(contractor_name);",
        "CREATE INDEX idx_np_issue ON normalized_permits(issue_date);",
        "CREATE INDEX idx_np_addr_city ON normalized_permits(normalized_address, city);",
        "CREATE INDEX idx_np_hail ON normalized_permits(is_hail_storm_window);",
        "CREATE INDEX idx_cc_city ON canonical_contractors(headquarters_city);",
        "CREATE INDEX idx_cc_val ON canonical_contractors(total_valuation DESC);",
    ]
    for idx_sql in indexes:
        local_cur.execute(idx_sql)
    local_conn.commit()
    local_conn.close()

    mb = os.path.getsize(LOCAL_DB_PATH) / (1024 * 1024)
    print(f"[{time.strftime('%X')}] SYNC COMPLETE! Local database: {LOCAL_DB_PATH} ({mb:.2f} MB)", flush=True)

if __name__ == "__main__":
    main()
