import sqlite3
import json
import urllib.request
import urllib.parse
import re
import time
from typing import Dict, Any, Optional

BORO_NUMS = {
    "MN": 1,
    "BX": 2,
    "BK": 3,
    "QN": 4,
    "SI": 5
}

def clean_street(raw_addr: str) -> str:
    """Extracts house number and primary street name from permit address."""
    s = raw_addr.upper().strip()
    s = re.sub(r"\b(STREET|ST|AVENUE|AVE|ROAD|RD|BOULEVARD|BLVD|PLACE|PL|WAY|DRIVE|DR|LANE|LN|NORTH|N|SOUTH|S|EAST|E|WEST|W)\b", "", s)
    s = re.sub(r"[^A-Z0-9\s]", "", s)
    parts = s.split()
    if len(parts) >= 2:
        return f"{parts[0]}%{parts[1]}"
    elif len(parts) == 1:
        return parts[0]
    return ""

def match_nyc_permits_to_pluto():
    db_path = "d:/projects/Roofx/depoii-data-engine/depoii_local.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get NYC permits that lack parcel_id
    cur.execute("""
        SELECT id, raw_permit_number, normalized_address, zip_code 
        FROM normalized_permits 
        WHERE jurisdiction = 'New York City, NY' AND (parcel_id IS NULL OR length(trim(parcel_id)) = 0)
        LIMIT 50
    """)
    permits = cur.fetchall()
    print(f"Targeting {len(permits)} NYC permits for PLUTO parcel resolution...")

    matched_count = 0
    parcels_inserted = 0

    for pid, pnum, address, zipcode in permits:
        # Extract search query
        clean_pattern = clean_street(address)
        if not clean_pattern:
            continue

        where_clause = f"Address LIKE '{clean_pattern}%'"
        if zipcode and zipcode != "00000" and len(zipcode) == 5:
            where_clause += f" AND ZipCode = {zipcode}"

        params = {
            'where': where_clause,
            'outFields': 'Borough,Block,Lot,Address,ZipCode,BldgArea,OwnerName,YearBuilt,AssessTot,BldgClass',
            'resultRecordCount': 1,
            'f': 'json'
        }
        url = 'https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query?' + urllib.parse.urlencode(params)
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Depoii-Matcher/1.0'})
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode())
                features = data.get('features', [])
                
                if features:
                    attr = features[0]['attributes']
                    boro = str(attr.get('Borough') or 'MN').strip()
                    boro_num = BORO_NUMS.get(boro, 1)
                    block = int(attr.get('Block') or 0)
                    lot = int(attr.get('Lot') or 0)
                    bbl = f"{boro_num}{block:05d}{lot:04d}"
                    parcel_id = f"NYC-PLUTO-{bbl}"
                    
                    owner_name = str(attr.get('OwnerName') or 'Institutional Real Estate Owner').strip().title()
                    bldg_sqft = int(attr.get('BldgArea') or 0)
                    year_built = int(attr.get('YearBuilt')) if attr.get('YearBuilt') and attr.get('YearBuilt') > 1800 else None
                    assess_tot = float(attr.get('AssessTot') or 0.0)
                    est_valuation = round(assess_tot * 2.22, 2) if assess_tot > 0 else round(bldg_sqft * 250.0, 2)
                    prop_addr = str(attr.get('Address') or address).strip().title()

                    # 1. Insert into parcels table
                    cur.execute("""
                        INSERT INTO parcels (
                            id, account_number, jurisdiction_id, jurisdiction, address, 
                            city, county, state, zip_code, building_sqft, year_built, 
                            owner_name, total_valuation, improvement_valuation, data_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET 
                            owner_name=excluded.owner_name,
                            building_sqft=excluded.building_sqft,
                            year_built=excluded.year_built
                    """, (
                        parcel_id, bbl, 'JUR-NYC-001', 'New York City, NY', prop_addr,
                        'New York City', 'New York', 'NY', str(attr.get('ZipCode') or zipcode),
                        bldg_sqft, year_built, owner_name, est_valuation, round(est_valuation * 0.8, 2),
                        'NYC Department of City Planning (MapPLUTO)'
                    ))
                    parcels_inserted += 1

                    # 2. Update permit record with parcel_id
                    cur.execute("""
                        UPDATE normalized_permits 
                        SET parcel_id = ? 
                        WHERE id = ?
                    """, (parcel_id, pid))
                    matched_count += 1
                    print(f" MATCHED: {pnum} ({address}) -> {parcel_id} | Owner: {owner_name} | SqFt: {bldg_sqft:,}")

        except Exception as e:
            # Continue on error
            pass
        
        time.sleep(0.05)

    conn.commit()
    print(f"\n--- Batch Match Complete ---")
    print(f"Permits matched and linked: {matched_count}/{len(permits)}")
    print(f"Parcels recorded in database: {parcels_inserted}")

if __name__ == '__main__':
    match_nyc_permits_to_pluto()
