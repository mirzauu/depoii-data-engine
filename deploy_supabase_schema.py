import psycopg2
import sys

CONNECTION_STRING = "postgresql://postgres:Alimirsa%40123@db.enbebudptwexwkxocgtv.supabase.co:5432/postgres"

DDL_STATEMENTS = """
-- 1. Enable PostGIS Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. States Table
CREATE TABLE IF NOT EXISTS states (
    code VARCHAR(2) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    region VARCHAR(30)
);

-- Seed Initial States
INSERT INTO states (code, name, region) VALUES
('TX', 'Texas', 'South'),
('OH', 'Ohio', 'Midwest'),
('WA', 'Washington', 'West'),
('FL', 'Florida', 'South'),
('MA', 'Massachusetts', 'Northeast'),
('NY', 'New York', 'Northeast'),
('MD', 'Maryland', 'Northeast'),
('LA', 'Louisiana', 'South'),
('CA', 'California', 'West'),
('IL', 'Illinois', 'Midwest')
ON CONFLICT (code) DO NOTHING;

-- 3. Jurisdictions Table
CREATE TABLE IF NOT EXISTS jurisdictions (
    id VARCHAR(50) PRIMARY KEY,
    state_code VARCHAR(2) NOT NULL REFERENCES states(code) ON DELETE RESTRICT,
    city_name VARCHAR(100) NOT NULL,
    county VARCHAR(100),
    portal_type VARCHAR(30) DEFAULT 'socrata',
    parcel_cad_source VARCHAR(100),
    center_point GEOMETRY(Point, 4326),
    total_permits INT DEFAULT 0,
    total_valuation_usd NUMERIC(15, 2) DEFAULT 0.00,
    has_active_storms BOOLEAN DEFAULT FALSE,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_state_city UNIQUE(state_code, city_name)
);

CREATE INDEX IF NOT EXISTS idx_jurisdictions_state ON jurisdictions(state_code);

-- 4. Canonical Contractors Table
CREATE TABLE IF NOT EXISTS canonical_contractors (
    id VARCHAR(100) PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL UNIQUE,
    primary_license VARCHAR(100),
    headquarters_city VARCHAR(100),
    headquarters_state VARCHAR(2) REFERENCES states(code),
    total_permits INT DEFAULT 0,
    total_valuation NUMERIC(15, 2) DEFAULT 0.00,
    primary_roof_system VARCHAR(100) DEFAULT 'TPO Single-Ply',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Contractor Aliases Table
CREATE TABLE IF NOT EXISTS contractor_aliases (
    id BIGSERIAL PRIMARY KEY,
    canonical_id VARCHAR(100) NOT NULL REFERENCES canonical_contractors(id) ON DELETE CASCADE,
    raw_name VARCHAR(255) NOT NULL,
    raw_license VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contractor_alias_raw ON contractor_aliases(raw_name);

-- 6. Storm Swaths Table
CREATE TABLE IF NOT EXISTS storm_swaths (
    id VARCHAR(100) PRIMARY KEY,
    storm_name VARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    max_hail_inches NUMERIC(4, 2) DEFAULT 2.00,
    max_gust_mph INT,
    jurisdiction_id VARCHAR(50) REFERENCES jurisdictions(id) ON DELETE SET NULL,
    geom_polygon GEOMETRY(MultiPolygon, 4326),
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_storm_swaths_date ON storm_swaths(event_date);

-- 7. Commercial Parcels Table
CREATE TABLE IF NOT EXISTS parcels (
    id VARCHAR(100) PRIMARY KEY,
    jurisdiction_id VARCHAR(50) REFERENCES jurisdictions(id) ON DELETE SET NULL,
    address VARCHAR(255) NOT NULL,
    state VARCHAR(2) NOT NULL REFERENCES states(code),
    city VARCHAR(100),
    zip_code VARCHAR(20) NOT NULL,
    building_sqft INT NOT NULL DEFAULT 0,
    year_built INT,
    property_type VARCHAR(100) DEFAULT 'Commercial Warehouse',
    owner_name VARCHAR(255) NOT NULL,
    geom_point GEOMETRY(Point, 4326),
    geom_polygon GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parcels_jurisdiction ON parcels(jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_parcels_sqft ON parcels(building_sqft);

-- 8. Normalized Permits Table
CREATE TABLE IF NOT EXISTS normalized_permits (
    id VARCHAR(120) PRIMARY KEY,
    raw_permit_number VARCHAR(100) NOT NULL,
    jurisdiction_id VARCHAR(50) REFERENCES jurisdictions(id) ON DELETE SET NULL,
    parcel_id VARCHAR(100) REFERENCES parcels(id) ON DELETE SET NULL,
    contractor_id VARCHAR(100) REFERENCES canonical_contractors(id) ON DELETE SET NULL,
    source_system VARCHAR(50) NOT NULL,
    jurisdiction VARCHAR(100) NOT NULL,
    state VARCHAR(10) NOT NULL,
    city VARCHAR(100) NOT NULL,
    issue_date DATE NOT NULL,
    applied_date DATE,
    expiration_date DATE,
    status VARCHAR(50) DEFAULT 'Active',
    normalized_address VARCHAR(255) NOT NULL,
    zip_code VARCHAR(20) NOT NULL,
    valuation NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    valuation_formatted VARCHAR(50) DEFAULT '$0',
    category VARCHAR(100) NOT NULL DEFAULT 'Commercial Re-Roof',
    probable_roof_system VARCHAR(100) NOT NULL DEFAULT 'Unspecified Commercial System',
    raw_description TEXT NOT NULL,
    square_footage INT,
    contractor_name VARCHAR(255) NOT NULL,
    contractor_license VARCHAR(100),
    contractor_phone VARCHAR(50),
    is_hail_storm_window BOOLEAN DEFAULT FALSE,
    associated_storm_id VARCHAR(100) REFERENCES storm_swaths(id) ON DELETE SET NULL,
    is_competitor_capture BOOLEAN DEFAULT TRUE,
    confidence_score INT DEFAULT 100,
    geom_point GEOMETRY(Point, 4326),
    normalized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_permit_record UNIQUE(raw_permit_number, jurisdiction, issue_date)
);

CREATE INDEX IF NOT EXISTS idx_permits_jurisdiction_date ON normalized_permits(jurisdiction_id, issue_date DESC);
CREATE INDEX IF NOT EXISTS idx_permits_state_city ON normalized_permits(state, city);
CREATE INDEX IF NOT EXISTS idx_permits_valuation ON normalized_permits(valuation DESC);
CREATE INDEX IF NOT EXISTS idx_permits_category ON normalized_permits(category);
CREATE INDEX IF NOT EXISTS idx_permits_contractor ON normalized_permits(contractor_name);

-- 9. Scraper & Sync Logs
CREATE TABLE IF NOT EXISTS sync_logs (
    id BIGSERIAL PRIMARY KEY,
    jurisdiction_id VARCHAR(50) REFERENCES jurisdictions(id) ON DELETE CASCADE,
    source_system VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    records_fetched INT DEFAULT 0,
    records_normalized INT DEFAULT 0,
    duplicates_removed INT DEFAULT 0,
    duration_seconds NUMERIC(8, 3) DEFAULT 0.000,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

def main():
    print("Connecting to Supabase PostgreSQL instance...")
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    print("Applying DDL statements...")
    cur.execute(DDL_STATEMENTS)
    conn.commit()
    print("DDL Migration applied successfully!")

    # Verify tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    print("Existing tables in Supabase public schema:")
    for t in tables:
        print(f" - {t[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
