import sqlite3
import httpx
import re

TAD_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"
DCAD_URL = "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/DallasTaxParcels/FeatureServer/0/query"

def parse_address_parts(addr_str: str):
    if not addr_str:
        return None, None
    clean = addr_str.split(",")[0].strip()
    m = re.match(r"^(\d+)\s+([A-Za-z0-9\s]+)$", clean)
    if m:
        num = m.group(1)
        street_raw = m.group(2).strip()
        # Remove suffix like ST, AVE, RD, BLVD, DR
        street_words = street_raw.split()
        if len(street_words) > 1 and street_words[-1].upper() in ["ST", "AVE", "RD", "BLVD", "DR", "PKWY", "LN", "WAY", "CIR", "TRL"]:
            street_name = " ".join(street_words[:-1])
        else:
            street_name = street_raw
        return num, street_name
    return None, None

def test_samples():
    conn = sqlite3.connect("depoii_local.db")
    cur = conn.cursor()
    
    # 1. Test Fort Worth sample
    cur.execute("SELECT id, normalized_address FROM normalized_permits WHERE jurisdiction LIKE '%Fort Worth%' AND (parcel_id IS NULL OR parcel_id = '') LIMIT 3")
    fw_permits = cur.fetchall()
    print("--- Testing Fort Worth Sample ---")
    for pid, addr in fw_permits:
        num, st = parse_address_parts(addr)
        print(f"Permit {pid}: {addr} -> Num: {num}, Street: {st}")
        if num and st:
            where = f"STREET_NO = {num} AND STREET_NAM LIKE '%{st}%'"
            try:
                r = httpx.get(TAD_URL, params={"where": where, "resultRecordCount": 1, "outFields": "ACCOUNT,OWNER_NAME,SITUS_ADDR,TOTAL_VALU,LIVING_ARE", "f": "json"}, timeout=10)
                feats = r.json().get("features", [])
                if feats:
                    print(f"  -> MATCHED TAD: {feats[0]['attributes']}")
                else:
                    print("  -> No TAD match")
            except Exception as e:
                print("  -> Error:", e)

    # 2. Test Dallas sample
    cur.execute("SELECT id, normalized_address FROM normalized_permits WHERE jurisdiction LIKE '%Dallas%' AND (parcel_id IS NULL OR parcel_id = '') LIMIT 3")
    dal_permits = cur.fetchall()
    print("\n--- Testing Dallas Sample ---")
    for pid, addr in dal_permits:
        num, st = parse_address_parts(addr)
        print(f"Permit {pid}: {addr} -> Num: {num}, Street: {st}")
        if num and st:
            where = f"ST_NUM = '{num}' AND ST_NAME LIKE '%{st}%'"
            try:
                r = httpx.get(DCAD_URL, params={"where": where, "resultRecordCount": 1, "outFields": "ACCT,TAXPANAME1,ST_NUM,ST_NAME,BUSNAME", "f": "json"}, timeout=10)
                feats = r.json().get("features", [])
                if feats:
                    print(f"  -> MATCHED DCAD: {feats[0]['attributes']}")
                else:
                    print("  -> No DCAD match")
            except Exception as e:
                print("  -> Error:", e)

if __name__ == "__main__":
    test_samples()
