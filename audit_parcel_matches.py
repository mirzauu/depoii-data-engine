import sqlite3

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables in DB:', tables)

# Check parcels table
if 'parcels' in tables:
    cur.execute('SELECT COUNT(*) FROM parcels')
    parcel_count = cur.fetchone()[0]
    print(f'Total parcels in parcels table: {parcel_count:,}')
    
    cur.execute('PRAGMA table_info(parcels)')
    cols = [c[1] for c in cur.fetchall()]
    print('Parcels columns:', cols)
else:
    print('No parcels table in DB')

# Check parcel_id in normalized_permits
cur.execute("SELECT COUNT(*) FROM normalized_permits WHERE parcel_id IS NOT NULL AND parcel_id != ''")
matched_permits = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM normalized_permits')
total_permits = cur.fetchone()[0]

print(f'Permits with parcel_id populated: {matched_permits:,} / {total_permits:,} ({matched_permits/total_permits*100:.2f}%)')

# Sample of populated parcel_ids
cur.execute("SELECT id, parcel_id, normalized_address, jurisdiction FROM normalized_permits WHERE parcel_id IS NOT NULL AND parcel_id != '' LIMIT 5")
samples = cur.fetchall()
print('Sample matched permits:', samples)
