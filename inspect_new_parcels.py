import sqlite3

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()
cur.execute("""
    SELECT id, owner_name, address, city, state, building_sqft, total_valuation, data_source
    FROM parcels
    WHERE id LIKE 'NYC-PLUTO-%'
    ORDER BY created_at DESC
    LIMIT 3
""")
for row in cur.fetchall():
    print("Parcel:", row[0])
    print("  Owner:", row[1])
    print("  Address:", row[2], f"({row[3]}, {row[4]})")
    print(f"  SqFt: {row[5]:,} | Valuation: ${row[6]:,.2f}")
    print("  Source:", row[7])
    print()
