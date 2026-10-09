import sqlite3
import json

companies = [
    {"rank": 1, "name": "LSR Multifamily", "id": "CTR-TX-LSR-MULTIFAMILY"},
    {"rank": 2, "name": "Onyx Commercial Roofing", "id": "CTR-DAL-ONYX-COMMERCIAL-ROOFING"},
    {"rank": 3, "name": "Hawk Sight Commercial Roofing", "id": "CTR-TX-HAWK-SIGHT-COMMERCIAL"},
    {"rank": 4, "name": "DFW Housing Partners", "id": "CTR-TX-DFW-HOUSING-PARTNERS"},
    {"rank": 5, "name": "MAZE Commercial Roofing & Construction", "id": "CTR-DAL-MAZE-ROOFING-CONSTRUCTION-LLC"},
    {"rank": 6, "name": "United Multifamily Construction", "id": "CTR-DAL-UNITED-MULTIFAMILY-CONSTRUCTION-INC"},
    {"rank": 7, "name": "US Prime Roofing", "id": "CTR-DAL-US-PRIME-ROOFING"},
    {"rank": 8, "name": "DFW Roofing Pro", "id": "CTR-DAL-DFW-ROOFING-PRO-LLC"},
    {"rank": 9, "name": "L&M Roofing", "id": "CTR-NIETO-CONTRACTORS-INC"},
    {"rank": 10, "name": "REVMA Roofing", "id": "CTR-NYC-REVMA-ROOFING"},
    {"rank": 11, "name": "Snap Roofing & Gutters", "id": "CTR-NYC-SNAP-ROOFING"},
    {"rank": 12, "name": "Apex Contracting Group", "id": "CTR-APEX-COMMERCIAL-TX"},
    {"rank": 13, "name": "Valentine Roofing", "id": "CTR-WA-VALENTINE-ROOFING"},
    {"rank": 14, "name": "K Single Corp", "id": "CTR-WA-K-SINGLE-CORP"},
    {"rank": 15, "name": "Molloy Roofing Company", "id": "CTR-OH-MOLLOY-ROOFING"},
    {"rank": 16, "name": "IC Roofing", "id": "CTR-OH-IC-ROOFING"},
    {"rank": 17, "name": "A-1 Roofing Co.", "id": "CTR-IL-A1-ROOFING-CO"},
    {"rank": 18, "name": "Americanstruction", "id": "CTR-IL-AMERICANSTRUCTION"},
    {"rank": 19, "name": "Crown Contracting", "id": "CTR-MA-CROWN-CONTRACTING"},
    {"rank": 20, "name": "S&K Roofing, Siding & Windows", "id": "CTR-MD-SK-ROOFING"}
]

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()

print("="*110)
print(f"{'#':<3} | {'COMPANY':<32} | {'CANONICAL ID':<38} | {'HQ':<18} | {'PERMIT #':<15}")
print("="*110)

for c in companies:
    cur.execute("SELECT canonical_name, headquarters_city, headquarters_state, phone_number, primary_license FROM canonical_contractors WHERE id = ?", (c["id"],))
    row = cur.fetchone()
    if row:
        cname, city, state, phone, lic = row
        cur.execute("SELECT raw_permit_number, valuation, issue_date FROM normalized_permits WHERE contractor_id = ? LIMIT 1", (c["id"],))
        prow = cur.fetchone()
        permit_str = prow[0] if prow else "N/A"
        loc = f"{city or ''}, {state or ''}".strip(", ")
        print(f"{c['rank']:<3} | {c['name']:<32} | {c['id']:<38} | {loc:<18} | {permit_str:<15}")

conn.close()
