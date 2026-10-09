import os
import sys
import time
import json
import sqlite3
import re
import argparse
from datetime import datetime, timezone
import httpx

DB_PATH = os.path.join(os.path.dirname(__file__), "depoii_local.db")
STATE_FILE = os.path.join(os.path.dirname(__file__), "parcel_batch_state.json")

# CAD Endpoints
PLUTO_URL = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query"
DCAD_URL = "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/DallasTaxParcels/FeatureServer/0/query"
TAD_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"

SUFFIXES = {"ST", "STREET", "AVE", "AVENUE", "RD", "ROAD", "BLVD", "BOULEVARD", "DR", "DRIVE",
            "PKWY", "PARKWAY", "LN", "LANE", "WAY", "CIR", "CIRCLE", "TRL", "TRAIL", "HWY", "HIGHWAY", "FWY", "FREEWAY"}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "current_offset": 0,
        "batch_size": 250,
        "completed_chunks": 0,
        "total_scanned": 0,
        "total_matched": 0,
        "total_parcels_created": 0,
        "status": "INITIALIZED",
        "last_batch_time": None,
        "next_scheduled_run": None
    }

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def clean_address_components(raw_addr: str) -> tuple:
    if not raw_addr:
        return None, None
    # Strip unit/suite/ste/#
    clean = re.sub(r",?\s*(?:ste|suite|apt|unit|bldg|fl|floor|#)\s*[:#]?\s*[\w\-]+.*$", "", raw_addr, flags=re.IGNORECASE)
    # Strip city/state suffix
    clean = re.split(r",\s*(?:Dallas|Fort Worth|New York|Brooklyn|Queens|Bronx|Manhattan|Staten Island|TX|NY)\b", clean, flags=re.IGNORECASE)[0].strip()
    
    m = re.match(r"^(\d+)\s+([A-Za-z0-9\s\.\-]+)$", clean)
    if m:
        num = m.group(1).strip()
        street_raw = m.group(2).strip()
        words = street_raw.split()
        if len(words) > 1 and words[-1].upper() in SUFFIXES:
            street_name = " ".join(words[:-1])
        else:
            street_name = street_raw
        # Strip directionals if isolated (e.g. "E SEMINARY" -> "SEMINARY")
        st_parts = street_name.split()
        if len(st_parts) > 1 and st_parts[0].upper() in ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]:
            street_name = " ".join(st_parts[1:])
        return num, street_name.strip()
    return None, None

def match_tarrant_tad(client: httpx.Client, num: str, street: str) -> dict:
    where = f"SITUS_ADDR LIKE '%{num}%{street}%'"
    params = {
        "where": where,
        "resultRecordCount": 1,
        "outFields": "ACCOUNT,TAXPIN,OWNER_NAME,OWNER_ADDR,SITUS_ADDR,TOTAL_VALU,IMPR_VALUE,LIVING_ARE,LAND_SQFT,YEAR_BUILT,CITY,STATE",
        "f": "json"
    }
    try:
        r = client.get(TAD_URL, params=params, timeout=12)
        if r.status_code == 200:
            feats = r.json().get("features", [])
            if feats:
                a = feats[0].get("attributes", {})
                acct = str(a.get("ACCOUNT") or "").strip()
                if acct:
                    return {
                        "id": f"FTW-TAD-{acct}",
                        "account_number": acct,
                        "jurisdiction_id": "TX-FORTWORTH",
                        "jurisdiction": "Fort Worth, TX",
                        "address": (a.get("SITUS_ADDR") or "").strip(),
                        "city": "Fort Worth",
                        "county": "Tarrant",
                        "state": "TX",
                        "zip_code": "76102",
                        "building_sqft": a.get("LIVING_ARE"),
                        "land_sqft": a.get("LAND_SQFT"),
                        "year_built": int(a["YEAR_BUILT"]) if a.get("YEAR_BUILT") else None,
                        "property_type": "Commercial",
                        "owner_name": (a.get("OWNER_NAME") or "").strip(),
                        "owner_address": (a.get("OWNER_ADDR") or "").strip(),
                        "total_valuation": a.get("TOTAL_VALU") or 0.0,
                        "improvement_valuation": a.get("IMPR_VALUE") or 0.0,
                        "data_source": "Tarrant Appraisal District (TAD)"
                    }
    except Exception:
        pass
    return None

def match_dallas_dcad(client: httpx.Client, num: str, street: str) -> dict:
    where = f"ST_NUM = '{num}' AND ST_NAME LIKE '%{street}%'"
    params = {
        "where": where,
        "resultRecordCount": 1,
        "outFields": "ACCT,TAXPANAME1,ST_NUM,ST_NAME,ST_TYPE,AREA_FEET,PROP_CL,BUSNAME,TAXPAZIP,Website",
        "f": "json"
    }
    try:
        r = client.get(DCAD_URL, params=params, timeout=12)
        if r.status_code == 200:
            feats = r.json().get("features", [])
            if feats:
                a = feats[0].get("attributes", {})
                acct = str(a.get("ACCT") or "").strip()
                if acct:
                    st_num = a.get("ST_NUM") or num
                    st_name = a.get("ST_NAME") or street
                    st_type = a.get("ST_TYPE") or ""
                    full_addr = f"{st_num} {st_name} {st_type}".strip()
                    owner = (a.get("TAXPANAME1") or a.get("BUSNAME") or "Commercial Property Owner").strip()
                    zip_c = str(a.get("TAXPAZIP") or "75201")[:5]
                    return {
                        "id": f"DAL-DCAD-{acct}",
                        "account_number": acct,
                        "jurisdiction_id": "TX-DALLAS",
                        "jurisdiction": "Dallas, TX",
                        "address": full_addr,
                        "city": "Dallas",
                        "county": "Dallas",
                        "state": "TX",
                        "zip_code": zip_c,
                        "building_sqft": None,
                        "land_sqft": a.get("AREA_FEET"),
                        "year_built": None,
                        "property_type": a.get("PROP_CL") or "Commercial",
                        "owner_name": owner,
                        "owner_address": full_addr,
                        "total_valuation": 0.0,
                        "improvement_valuation": 0.0,
                        "data_source": "Dallas Central Appraisal District (DCAD)"
                    }
    except Exception:
        pass
    return None

def match_nyc_pluto(client: httpx.Client, num: str, street: str) -> dict:
    where = f"Address LIKE '%{num}%{street}%'"
    params = {
        "where": where,
        "resultRecordCount": 1,
        "outFields": "BBL,Address,OwnerName,BldgArea,LotArea,AssessTot,YearBuilt,ZipCode,BldgClass,Latitude,Longitude",
        "f": "json"
    }
    try:
        r = client.get(PLUTO_URL, params=params, timeout=12)
        if r.status_code == 200:
            feats = r.json().get("features", [])
            if feats:
                a = feats[0].get("attributes", {})
                bbl = str(a.get("BBL") or "").strip()
                if bbl:
                    return {
                        "id": f"NYC-PLUTO-{bbl}",
                        "account_number": bbl,
                        "jurisdiction_id": "NY-NYC",
                        "jurisdiction": "New York City, NY",
                        "address": (a.get("Address") or "").strip(),
                        "city": "New York",
                        "county": "New York",
                        "state": "NY",
                        "zip_code": str(a.get("ZipCode") or "10001")[:5],
                        "building_sqft": a.get("BldgArea"),
                        "land_sqft": a.get("LotArea"),
                        "year_built": int(a["YearBuilt"]) if a.get("YearBuilt") else None,
                        "property_type": a.get("BldgClass") or "Commercial",
                        "owner_name": (a.get("OwnerName") or "NYC Property Owner").strip(),
                        "owner_address": (a.get("Address") or "").strip(),
                        "total_valuation": float(a.get("AssessTot") or 0.0),
                        "improvement_valuation": 0.0,
                        "latitude": a.get("Latitude"),
                        "longitude": a.get("Longitude"),
                        "data_source": "NYC MapPLUTO (Department of City Planning)"
                    }
    except Exception:
        pass
    return None

def process_batch(offset: int = 0, batch_size: int = 250) -> tuple:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Select unlinked permits for our target CAD jurisdictions
    cur.execute("""
        SELECT id, jurisdiction, normalized_address, latitude, longitude
        FROM normalized_permits
        WHERE (parcel_id IS NULL OR parcel_id = '')
          AND (jurisdiction LIKE '%Fort Worth%' OR jurisdiction LIKE '%Dallas%' OR jurisdiction LIKE '%New York%')
        LIMIT ? OFFSET ?
    """, (batch_size, offset))
    rows = cur.fetchall()
    
    if not rows:
        conn.close()
        return 0, 0, 0
        
    matched_count = 0
    parcels_created = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    
    with httpx.Client(timeout=15.0) as client:
        for pid, jur, addr, lat, lon in rows:
            num, street = clean_address_components(addr)
            if not num or not street:
                continue
                
            parcel_data = None
            jur_lower = (jur or "").lower()
            
            if "fort worth" in jur_lower:
                parcel_data = match_tarrant_tad(client, num, street)
            elif "dallas" in jur_lower:
                parcel_data = match_dallas_dcad(client, num, street)
            elif "new york" in jur_lower or "brooklyn" in jur_lower or "queens" in jur_lower:
                parcel_data = match_nyc_pluto(client, num, street)
                
            if parcel_data:
                # Upsert into parcels table
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO parcels (
                            id, account_number, jurisdiction_id, jurisdiction, address,
                            city, county, state, zip_code, building_sqft, land_sqft,
                            year_built, property_type, owner_name, owner_address,
                            total_valuation, improvement_valuation, latitude, longitude,
                            data_source, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        parcel_data["id"], parcel_data["account_number"], parcel_data["jurisdiction_id"],
                        parcel_data["jurisdiction"], parcel_data["address"], parcel_data["city"],
                        parcel_data["county"], parcel_data["state"], parcel_data["zip_code"],
                        parcel_data["building_sqft"], parcel_data["land_sqft"], parcel_data["year_built"],
                        parcel_data["property_type"], parcel_data["owner_name"], parcel_data["owner_address"],
                        parcel_data["total_valuation"], parcel_data["improvement_valuation"],
                        parcel_data.get("latitude") or lat, parcel_data.get("longitude") or lon,
                        parcel_data["data_source"], now_iso
                    ))
                    parcels_created += 1
                except Exception:
                    pass
                    
                # Link permit to parcel
                try:
                    cur.execute("UPDATE normalized_permits SET parcel_id = ? WHERE id = ?", (parcel_data["id"], pid))
                    matched_count += 1
                except Exception:
                    pass
                    
    conn.commit()
    conn.close()
    return len(rows), matched_count, parcels_created

def run_single_batch() -> dict:
    state = load_state()
    offset = state.get("current_offset", 0)
    batch_size = state.get("batch_size", 250)
    
    print(f"\n=======================================================")
    print(f" [Parcel Matcher] Scanning {batch_size} unlinked permits (Offset: {offset:,})...")
    print(f"=======================================================")
    
    t0 = time.time()
    scanned, matched, created = process_batch(offset, batch_size)
    elapsed = time.time() - t0
    
    state["current_offset"] = offset + scanned
    state["total_scanned"] += scanned
    state["total_matched"] += matched
    state["total_parcels_created"] += created
    state["completed_chunks"] += 1
    state["last_batch_time"] = datetime.now(timezone.utc).isoformat()
    
    if scanned == 0:
        print("All permits have been evaluated for parcel matching!")
        state["status"] = "COMPLETED"
        state["next_scheduled_run"] = None
    else:
        state["status"] = "SLEEPING"
        state["next_scheduled_run"] = datetime.fromtimestamp(time.time() + 300, timezone.utc).isoformat()
        
    save_state(state)
    print(f"-> Batch completed in {elapsed:.2f}s! Scanned {scanned:,} permits | Matched & Linked: {matched:,} | New Parcels: {created:,}")
    return state

def run_daemon(interval_sec: int = 300):
    state = load_state()
    print("=================================================================")
    print(" Starting Automated Tax Parcel Harvester & Matching Daemon")
    print(f" Interval Pause: {interval_sec} seconds (5.0 minutes)")
    print(f" Batch Size     : {state.get('batch_size', 250)} permits/batch")
    print("=================================================================")
    
    while state.get("status") != "COMPLETED":
        try:
            state["status"] = "RUNNING"
            save_state(state)
            state = run_single_batch()
            
            if state.get("status") == "COMPLETED":
                print("\nAll permit-to-parcel matching batches completed successfully!")
                break
                
            print(f"\n[DAEMON] Sleeping for {interval_sec} seconds (5 minutes)...")
            print(f"[DAEMON] Next batch scheduled at: {state.get('next_scheduled_run')}")
            time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\nDaemon paused gracefully by operator.")
            state["status"] = "PAUSED"
            save_state(state)
            break
        except Exception as e:
            print(f"Unexpected error in daemon loop: {e}")
            time.sleep(60)

def print_status():
    state = load_state()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM normalized_permits")
    total_permits = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE parcel_id IS NOT NULL AND parcel_id != ''")
    matched_permits = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM parcels")
    total_parcels = cur.fetchone()[0]
    
    cur.execute("SELECT jurisdiction, COUNT(*) FROM parcels GROUP BY jurisdiction ORDER BY COUNT(*) DESC")
    parcels_by_jur = cur.fetchall()
    
    conn.close()
    
    pct = (matched_permits / total_permits * 100) if total_permits > 0 else 0.0
    
    print("\n========================================================")
    print("  TAX PARCEL HARVESTING & PERMIT-MATCHING STATUS")
    print("========================================================")
    print(f"Daemon Status           : {state.get('status')}")
    print(f"Batches Completed       : {state.get('completed_chunks', 0)}")
    print(f"Total Parcels in DB     : {total_parcels:,}")
    print(f"Matched Permits in DB   : {matched_permits:,} / {total_permits:,} ({pct:.2f}%)")
    print(f"Unmatched Permits       : {total_permits - matched_permits:,}")
    print(f"Last Batch Finished     : {state.get('last_batch_time')}")
    print(f"Next Batch Scheduled    : {state.get('next_scheduled_run')}")
    print("\n--- Parcels by Jurisdiction ---")
    for jur, cnt in parcels_by_jur:
        print(f"  • {jur:<25}: {cnt:>6,} parcels")
    print("========================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Tax Parcel Harvester & Matcher")
    parser.add_argument("--daemon", action="store_true", help="Run background daemon with 5-minute interval")
    parser.add_argument("--once", action="store_true", help="Execute single batch chunk and stop")
    parser.add_argument("--status", action="store_true", help="Show current live status")
    parser.add_argument("--reset", action="store_true", help="Reset batch checkpoint")
    parser.add_argument("--interval", type=int, default=300, help="Interval seconds (default 300 / 5 min)")
    parser.add_argument("--batch-size", type=int, default=250, help="Permits per batch chunk (default 250)")
    args = parser.parse_args()

    if args.reset:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        print("Reset parcel matcher state.")
        sys.exit(0)
    if args.status:
        print_status()
        sys.exit(0)
    if args.once:
        run_single_batch()
        sys.exit(0)
    if args.daemon:
        run_daemon(args.interval)
    else:
        parser.print_help()
