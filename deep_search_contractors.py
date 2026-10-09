import sqlite3

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()

def deep_search(keyword):
    print(f"\n=================== Deep Search: '{keyword}' ===================")
    # Search canonical_contractors
    cur.execute("""
        SELECT id, canonical_name, headquarters_city, headquarters_state, total_permits, total_valuation, website_url
        FROM canonical_contractors
        WHERE UPPER(canonical_name) LIKE ?
           OR UPPER(id) LIKE ?
           OR UPPER(COALESCE(website_url, '')) LIKE ?
    """, (f"%{keyword.upper()}%", f"%{keyword.upper()}%", f"%{keyword.upper()}%"))
    c_rows = cur.fetchall()
    print(f"  Canonical Contractors ({len(c_rows)}):")
    for r in c_rows[:10]:
        print(f"    - ID: {r[0]} | Name: {r[1]} | Loc: {r[2]}, {r[3]} | Permits: {r[4]} | Val: ${r[5]:,.2f} | Web: {r[6]}")
        
    # Search normalized_permits contractor_name
    cur.execute("""
        SELECT contractor_id, contractor_name, jurisdiction, state, COUNT(*) as cnt, SUM(valuation) as val
        FROM normalized_permits
        WHERE UPPER(contractor_name) LIKE ?
        GROUP BY contractor_name, jurisdiction, state
        ORDER BY cnt DESC
    """, (f"%{keyword.upper()}%",))
    p_rows = cur.fetchall()
    print(f"  Normalized Permits ({len(p_rows)}):")
    for r in p_rows[:10]:
        print(f"    - Raw Name: {r[1]} (CID: {r[0]}) | Jur: {r[2]} ({r[3]}) | Permits: {r[4]} | Val: ${r[5]:,.2f}")

# Check specific queries
deep_search("LSR")
deep_search("ONYX")
deep_search("HAWK SIGHT")
deep_search("HAWKSIGHT")
deep_search("HOUSING PARTNER")
deep_search("MAZE")
deep_search("UNITED MULTIFAMILY")
deep_search("US PRIME")
deep_search("DFW ROOFING PRO")
deep_search("L&M ROOF")
deep_search("LM ROOF")
deep_search("REVMA")
deep_search("SNAP ROOF")
deep_search("APEX CONTRACTING")
deep_search("VALENTINE")
deep_search("K SINGLE")
deep_search("KSINGLE")
deep_search("MOLLOY")
deep_search("IC ROOF")
deep_search("A-1 ROOF")
deep_search("A1 ROOF")
deep_search("AMERICANSTRUCTION")
deep_search("CROWN CONTRACT")
deep_search("S&K")
deep_search("SK ROOF")

conn.close()
