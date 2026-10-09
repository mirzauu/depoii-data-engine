import sqlite3
from batch_parcel_matcher import clean_address_components

conn = sqlite3.connect('depoii_local.db')
cur = conn.cursor()
cur.execute("SELECT id, jurisdiction, normalized_address FROM normalized_permits WHERE (parcel_id IS NULL OR parcel_id = '') LIMIT 10")
for row in cur.fetchall():
    num, street = clean_address_components(row[2])
    print(f"{row[0]} | Jur: '{row[1]}' | Addr: '{row[2]}' -> Num: {num}, Street: {street}")
