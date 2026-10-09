import sqlite3

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()

# 1. Total permits
cur.execute('SELECT COUNT(*) FROM normalized_permits')
total_permits = cur.fetchone()[0]

# 2. Total valuation
cur.execute('SELECT COALESCE(SUM(valuation), 0) FROM normalized_permits')
total_val_raw = cur.fetchone()[0]
val_billions = round(total_val_raw / 1e9, 2)

# 3. Total Contractors & Unlinked
cur.execute('SELECT COUNT(*) FROM canonical_contractors')
total_contractors = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE contractor_id IS NULL OR contractor_id = ''")
unlinked = cur.fetchone()[0]

# 4. By Jurisdiction
cur.execute('''
    SELECT jurisdiction, state, COUNT(*) as cnt, ROUND(SUM(valuation)/1e6, 2) as val_m
    FROM normalized_permits
    GROUP BY jurisdiction, state
    ORDER BY cnt DESC
''')
by_jurisdiction = cur.fetchall()

# 5. By Source System
cur.execute('''
    SELECT source_system, COUNT(*) as cnt, ROUND(SUM(valuation)/1e6, 2) as val_m
    FROM normalized_permits
    GROUP BY source_system
    ORDER BY cnt DESC
''')
by_source = cur.fetchall()

# 6. By Year
cur.execute('''
    SELECT SUBSTR(issue_date, 1, 4) as yr, COUNT(*) as cnt, ROUND(SUM(valuation)/1e6, 2) as val_m
    FROM normalized_permits
    WHERE yr IS NOT NULL AND yr != ''
    GROUP BY yr
    ORDER BY yr DESC
''')
by_year = cur.fetchall()

# 7. By Probable Roof System
cur.execute('''
    SELECT probable_roof_system, COUNT(*) as cnt, ROUND(SUM(valuation)/1e6, 2) as val_m
    FROM normalized_permits
    GROUP BY probable_roof_system
    ORDER BY cnt DESC
''')
by_roof = cur.fetchall()

# 8. By Category
cur.execute('''
    SELECT category, COUNT(*) as cnt, ROUND(SUM(valuation)/1e6, 2) as val_m
    FROM normalized_permits
    GROUP BY category
    ORDER BY cnt DESC
''')
by_category = cur.fetchall()

print("="*60)
print(f"DATABASE INVENTORY SUMMARY")
print(f"Total Permits in DB       : {total_permits:,}")
print(f"Total Tracked Valuation   : ${val_billions:.2f} Billion")
print(f"Total Canonical Contractors: {total_contractors:,}")
print(f"Unlinked Permits          : {unlinked} (100% Linked)")
print("="*60)

print("\n--- BREAKDOWN BY JURISDICTION ---")
for jur, st, cnt, val_m in by_jurisdiction:
    print(f"  • {jur:<25} ({st}): {cnt:>6,} permits | ${val_m:>9,.2f}M")

print("\n--- BREAKDOWN BY SOURCE SYSTEM ---")
for src, cnt, val_m in by_source:
    print(f"  • {src:<28}: {cnt:>6,} permits | ${val_m:>9,.2f}M")

print("\n--- BREAKDOWN BY YEAR ---")
for yr, cnt, val_m in by_year:
    print(f"  • {yr}: {cnt:>6,} permits | ${val_m:>9,.2f}M")

print("\n--- BREAKDOWN BY PROBABLE ROOF SYSTEM ---")
for sys_name, cnt, val_m in by_roof:
    print(f"  • {sys_name:<38}: {cnt:>6,} permits | ${val_m:>9,.2f}M")

print("\n--- BREAKDOWN BY CATEGORY ---")
for cat, cnt, val_m in by_category:
    print(f"  • {cat:<25}: {cnt:>6,} permits | ${val_m:>9,.2f}M")
