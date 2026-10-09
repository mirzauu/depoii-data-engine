import httpx

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'

# Check Subtypes of Commercial Building Permit
params_sub = {
    'where': "Permit_Type = 'Commercial Building Permit'",
    'outFields': 'Permit_SubType',
    'returnDistinctValues': 'true',
    'f': 'json'
}
r = httpx.get(url, params=params_sub, timeout=20)
if r.status_code == 200:
    subtypes = [f['attributes']['Permit_SubType'] for f in r.json().get('features', []) if f.get('attributes')]
    print('Subtypes of Commercial Building Permit:', subtypes)

# Test date filter syntax
test_dates = [
    "File_Date >= date '2024-01-01'",
    "File_Date >= TIMESTAMP '2024-01-01 00:00:00'",
    "Permit_No LIKE 'PB24-%' OR Permit_No LIKE 'PB25-%' OR Permit_No LIKE 'PB26-%'"
]

for d in test_dates:
    where = f"Permit_Type = 'Commercial Building Permit' AND ({d})"
    r_test = httpx.get(url, params={'where': where, 'returnCountOnly': 'true', 'f': 'json'}, timeout=20)
    print(f"Where [{d}]: {r_test.text}")
