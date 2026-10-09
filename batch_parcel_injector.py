import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
import httpx
import psycopg2
from psycopg2.extras import execute_values

CONNECTION_STRING = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:Alimirsa%40123@db.enbebudptwexwkxocgtv.supabase.co:5432/postgres"
)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parcel_batch_scheduler_state.json")

# 10 Locations across DFW Commercial Corridors
LOCATIONS = [
    {
        "id": 1,
        "name": "West Dallas Industrial Corridor",
        "zip": "75212",
        "city": "Dallas",
        "jurisdiction_id": "TX-DALLAS",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75212%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 2,
        "name": "Great Southwest Industrial District",
        "zip": "75050",
        "city": "Grand Prairie",
        "jurisdiction_id": "TX-GRAND_PRAIRIE",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75050%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 3,
        "name": "Stemmons Freeway / Brookhollow Logistics",
        "zip": "75247",
        "city": "Dallas",
        "jurisdiction_id": "TX-DALLAS",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75247%' AND AREA_FEET > 12000",
        "target_count": 35
    },
    {
        "id": 4,
        "name": "Carrollton Industrial Corridor",
        "zip": "75006",
        "city": "Carrollton",
        "jurisdiction_id": "TX-CARROLLTON",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75006%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 5,
        "name": "Addison Airport & Commercial Corridor",
        "zip": "75001",
        "city": "Addison",
        "jurisdiction_id": "TX-ADDISON",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75001%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 6,
        "name": "Farmers Branch Distribution Hub",
        "zip": "75234",
        "city": "Farmers Branch",
        "jurisdiction_id": "TX-FARMERS_BRANCH",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75234%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 7,
        "name": "Irving / Las Colinas Commercial Corridor",
        "zip": "75062",
        "city": "Irving",
        "jurisdiction_id": "TX-IRVING",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75062%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 8,
        "name": "Dallas Design District & Trinity Logistics",
        "zip": "75207",
        "city": "Dallas",
        "jurisdiction_id": "TX-DALLAS",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75207%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 9,
        "name": "North Dallas / Galleria Commercial Zone",
        "zip": "75244",
        "city": "Dallas",
        "jurisdiction_id": "TX-DALLAS",
        "county": "Dallas County",
        "cad_source": "Dallas CAD",
        "type": "dallas",
        "where": "ResCom = 'C' AND TAXPAZIP LIKE '75244%' AND AREA_FEET > 10000",
        "target_count": 35
    },
    {
        "id": 10,
        "name": "Downtown Fort Worth Commercial Center",
        "zip": "76102",
        "city": "Fort Worth",
        "jurisdiction_id": "TX-FORT_WORTH",
        "county": "Tarrant County",
        "cad_source": "Tarrant CAD",
        "type": "tarrant",
        "where": "TOTAL_VALU > 1000000 AND LIVING_ARE > 15000 AND CITY LIKE 'FORT WORTH%'",
        "target_count": 25
    }
]

# 5 Batches (2 locations per batch)
BATCHES = [
    {"batch_number": 1, "locations": [1, 2], "title": "Batch 1: West Dallas (75212) & Grand Prairie (75050)"},
    {"batch_number": 2, "locations": [3, 4], "title": "Batch 2: Stemmons Brookhollow (75247) & Carrollton (75006)"},
    {"batch_number": 3, "locations": [5, 6], "title": "Batch 3: Addison Airport (75001) & Farmers Branch (75234)"},
    {"batch_number": 4, "locations": [7, 8], "title": "Batch 4: Irving Las Colinas (75062) & Design District (75207)"},
    {"batch_number": 5, "locations": [9, 10], "title": "Batch 5: North Dallas (75244) & Downtown Fort Worth (76102)"},
]

DALLAS_URL = "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/DallasTaxParcels/FeatureServer/0/query"
TARRANT_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"

def rings_to_multipolygon_wkt(rings):
    if not rings:
        return None, None
    poly_strs = []
    all_points = []
    for ring in rings:
        if len(ring) < 3:
            continue
        if ring[0] != ring[-1]:
            ring = list(ring) + [ring[0]]
        pt_strs = [f"{p[0]} {p[1]}" for p in ring]
        poly_strs.append(f"(({', '.join(pt_strs)}))")
        all_points.extend(ring)

    if not poly_strs or not all_points:
        return None, None

    multi_wkt = f"SRID=4326;MULTIPOLYGON({', '.join(poly_strs)})"
    avg_lon = sum(p[0] for p in all_points) / len(all_points)
    avg_lat = sum(p[1] for p in all_points) / len(all_points)
    point_wkt = f"SRID=4326;POINT({avg_lon} {avg_lat})"
    return point_wkt, multi_wkt

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Default initial state
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_batch_index": 0,
        "total_batches": len(BATCHES),
        "total_locations": len(LOCATIONS),
        "completed_batches": [],
        "completed_locations": [],
        "total_parcels_inserted": 0,
        "is_all_completed": False,
        "runs": []
    }

def save_state(state):
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def fetch_dallas_parcels(client, loc):
    params = {
        "where": loc["where"],
        "outFields": "OBJECTID,ACCT,GIS_ACCT,ST_NUM,ST_NAME,ST_TYPE,CITY,COUNTY,BUSNAME,TAXPANAME1,PROPNAM,AREA_FEET,ResCom,BLDG_CL,APPRAISALYEAR,TAXPAZIP,Shape__Area",
        "resultRecordCount": str(loc["target_count"]),
        "f": "json",
        "returnGeometry": "true",
        "outSR": "4326"
    }
    resp = client.get(DALLAS_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
    data = resp.json()
    features = data.get("features", [])
    rows = []
    for f in features:
        attrs = f.get("attributes", {})
        geom = f.get("geometry", {})
        pt_wkt, poly_wkt = rings_to_multipolygon_wkt(geom.get("rings", []))
        if not pt_wkt:
            continue
        
        acct = str(attrs.get("ACCT") or attrs.get("OBJECTID")).strip()
        parcel_id = f"TX-DAL-{acct}"
        st_num = str(attrs.get("ST_NUM") or "").strip()
        st_name = str(attrs.get("ST_NAME") or "").strip()
        st_type = str(attrs.get("ST_TYPE") or "").strip()
        address = f"{st_num} {st_name} {st_type}".strip() or f"Commercial Property {acct}"
        
        owner = str(attrs.get("TAXPANAME1") or attrs.get("BUSNAME") or "Commercial Property Owner").strip()
        sqft = int(float(attrs.get("AREA_FEET") or attrs.get("Shape__Area") or 25000))
        year_built = int(attrs.get("APPRAISALYEAR") or 1998)
        prop_type = str(attrs.get("BLDG_CL") or "Commercial Warehouse").strip()
        
        rows.append({
            "id": parcel_id,
            "jurisdiction_id": loc["jurisdiction_id"],
            "address": address,
            "state": "TX",
            "city": loc["city"],
            "zip_code": loc["zip"],
            "building_sqft": sqft,
            "year_built": year_built,
            "property_type": prop_type,
            "owner_name": owner,
            "geom_point": pt_wkt,
            "geom_polygon": poly_wkt,
            "data_source": "Dallas CAD",
            "account_number": acct,
            "county": loc["county"]
        })
    return rows

def fetch_tarrant_parcels(client, loc):
    params = {
        "where": loc["where"],
        "outFields": "OBJECTID,ACCOUNT,SITUS_ADDR,CITY,OWNER_NAME,OWNER_ZIP,LIVING_ARE,TOTAL_VALU,YEAR_BUILT,DESCR",
        "resultRecordCount": str(loc["target_count"]),
        "f": "json",
        "returnGeometry": "true",
        "outSR": "4326"
    }
    resp = client.get(TARRANT_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
    data = resp.json()
    features = data.get("features", [])
    rows = []
    for f in features:
        attrs = f.get("attributes", {})
        geom = f.get("geometry", {})
        pt_wkt, poly_wkt = rings_to_multipolygon_wkt(geom.get("rings", []))
        if not pt_wkt:
            continue
        
        acct = str(attrs.get("ACCOUNT") or attrs.get("OBJECTID")).strip()
        parcel_id = f"TX-TAR-{acct}"
        address = str(attrs.get("SITUS_ADDR") or f"Commercial Property {acct}").strip()
        owner = str(attrs.get("OWNER_NAME") or "Commercial Property Owner").strip()
        sqft = int(float(attrs.get("LIVING_ARE") or 25000))
        year_built = int(float(attrs.get("YEAR_BUILT") or 1990)) if attrs.get("YEAR_BUILT") else 1990
        prop_type = str(attrs.get("DESCR") or "Commercial Warehouse").strip()
        total_val = float(attrs.get("TOTAL_VALU") or 1500000.0)
        
        rows.append({
            "id": parcel_id,
            "jurisdiction_id": loc["jurisdiction_id"],
            "address": address,
            "state": "TX",
            "city": loc["city"],
            "zip_code": loc["zip"],
            "building_sqft": sqft,
            "year_built": year_built,
            "property_type": prop_type,
            "owner_name": owner,
            "geom_point": pt_wkt,
            "geom_polygon": poly_wkt,
            "data_source": "Tarrant CAD",
            "account_number": acct,
            "county": loc["county"],
            "total_valuation": total_val
        })
    return rows

def insert_parcels(cur, parcel_rows):
    if not parcel_rows:
        return 0
    insert_sql = """
    INSERT INTO parcels (
        id, jurisdiction_id, address, state, city, zip_code,
        building_sqft, year_built, property_type, owner_name,
        geom_point, geom_polygon, data_source, account_number, county,
        total_valuation, updated_at
    ) VALUES (
        %(id)s, %(jurisdiction_id)s, %(address)s, %(state)s, %(city)s, %(zip_code)s,
        %(building_sqft)s, %(year_built)s, %(property_type)s, %(owner_name)s,
        ST_GeomFromEWKT(%(geom_point)s), ST_Multi(ST_GeomFromEWKT(%(geom_polygon)s)),
        %(data_source)s, %(account_number)s, %(county)s,
        %(total_valuation)s, NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        address = EXCLUDED.address,
        building_sqft = EXCLUDED.building_sqft,
        year_built = EXCLUDED.year_built,
        property_type = EXCLUDED.property_type,
        owner_name = EXCLUDED.owner_name,
        geom_point = EXCLUDED.geom_point,
        geom_polygon = EXCLUDED.geom_polygon,
        total_valuation = EXCLUDED.total_valuation,
        updated_at = NOW();
    """
    inserted = 0
    for r in parcel_rows:
        if "total_valuation" not in r:
            r["total_valuation"] = None
        cur.execute(insert_sql, r)
        inserted += 1
    return inserted

def process_batch(batch_idx):
    state = load_state()
    if batch_idx >= len(BATCHES):
        print(f"All {len(BATCHES)} batches already completed!")
        state["is_all_completed"] = True
        save_state(state)
        return False

    batch = BATCHES[batch_idx]
    batch_num = batch["batch_number"]
    print(f"\n=======================================================")
    print(f"[RUNNING] EXECUTING BATCH {batch_num}/{len(BATCHES)}: {batch['title']}")
    print(f"=======================================================\n")

    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()

    total_batch_parcels = 0
    loc_summaries = []

    with httpx.Client(timeout=30.0, verify=False) as client:
        for loc_id in batch["locations"]:
            loc = next(l for l in LOCATIONS if l["id"] == loc_id)
            print(f"[QUERY] Querying {loc['name']} (ZIP {loc['zip']} - {loc['cad_source']})...")
            
            t0 = time.time()
            if loc["type"] == "dallas":
                rows = fetch_dallas_parcels(client, loc)
            else:
                rows = fetch_tarrant_parcels(client, loc)
            
            inserted = insert_parcels(cur, rows)
            conn.commit()
            duration = round(time.time() - t0, 2)
            
            print(f"   [OK] Injected {inserted} commercial parcels into Supabase for {loc['city']} (ZIP {loc['zip']}) in {duration}s.")
            total_batch_parcels += inserted
            loc_summaries.append({
                "location_id": loc["id"],
                "name": loc["name"],
                "zip": loc["zip"],
                "city": loc["city"],
                "cad_source": loc["cad_source"],
                "parcels_injected": inserted,
                "duration_sec": duration
            })
            if loc["id"] not in state["completed_locations"]:
                state["completed_locations"].append(loc["id"])

    # Update state
    state["current_batch_index"] = batch_idx + 1
    if batch_num not in state["completed_batches"]:
        state["completed_batches"].append(batch_num)
    state["total_parcels_inserted"] += total_batch_parcels
    
    run_record = {
        "batch_number": batch_num,
        "batch_title": batch["title"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parcels_injected": total_batch_parcels,
        "locations": loc_summaries
    }
    state["runs"].append(run_record)

    if len(state["completed_batches"]) >= len(BATCHES):
        state["is_all_completed"] = True
        print(f"\n[DONE] ALL {len(LOCATIONS)} LOCATIONS AND {len(BATCHES)} BATCHES ARE NOW FULLY INJECTED!\n")

    save_state(state)

    # Verify total parcels in DB
    cur.execute("SELECT count(*) FROM parcels WHERE state = 'TX';")
    tx_parcels = cur.fetchone()[0]
    cur.execute("SELECT count(DISTINCT zip_code) FROM parcels WHERE state = 'TX';")
    tx_zips = cur.fetchone()[0]
    print(f"[DB STATUS] Current DB Status: {tx_parcels:,} TX commercial parcels across {tx_zips} ZIP codes in Supabase.")

    cur.close()
    conn.close()
    return True

def show_status():
    state = load_state()
    print("\n================ PARCEL INGESTION SCHEDULER STATUS ================")
    print(f"Status:             {'COMPLETED [DONE]' if state.get('is_all_completed') else 'IN PROGRESS [PENDING]'}")
    print(f"Batches Completed:  {len(state.get('completed_batches', []))}/{len(BATCHES)}")
    print(f"Locations Done:     {len(state.get('completed_locations', []))}/{len(LOCATIONS)}")
    print(f"Total Injected:     {state.get('total_parcels_inserted', 0):,} parcels")
    print(f"Next Batch Index:   {state.get('current_batch_index', 0) + 1}")
    print("\nLocations Breakdown:")
    for l in LOCATIONS:
        done = l["id"] in state.get("completed_locations", [])
        status_sym = "[DONE]" if done else "[PENDING]"
        print(f"  [{l['id']:02d}] {status_sym} - {l['name']} (ZIP: {l['zip']}, City: {l['city']}, Source: {l['cad_source']})")
    print("====================================================================\n")

def reset_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print("Scheduler state reset.")

def main():
    parser = argparse.ArgumentParser(description="DFW 10-Location Parcel Batch Scheduler")
    parser.add_argument("--run-next", action="store_true", help="Execute the next pending batch")
    parser.add_argument("--status", action="store_true", help="Show current ingestion status")
    parser.add_argument("--reset", action="store_true", help="Reset scheduler state")
    parser.add_argument("--batch", type=int, help="Run a specific batch number (1-5)")
    args = parser.parse_args()

    if args.reset:
        reset_state()
        return

    if args.status:
        show_status()
        return

    if args.batch:
        process_batch(args.batch - 1)
        return

    # Default: run-next
    state = load_state()
    idx = state.get("current_batch_index", 0)
    process_batch(idx)

if __name__ == "__main__":
    main()
