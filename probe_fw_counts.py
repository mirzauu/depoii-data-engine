import httpx

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'

queries = [
    ("Commercial Building Permit", "Permit_Type = 'Commercial Building Permit'"),
    ("Commercial Building Permit (2024-2026)", "Permit_Type = 'Commercial Building Permit' AND File_Date >= 1704067200000"),
    ("Commercial Building Permit (2025-2026)", "Permit_Type = 'Commercial Building Permit' AND File_Date >= 1735689600000"),
    ("Commercial Building Permit (2026 Live)", "Permit_Type = 'Commercial Building Permit' AND File_Date >= 1767225600000"),
]

for name, where in queries:
    params = {
        'where': where,
        'returnCountOnly': 'true',
        'f': 'json'
    }
    r = httpx.get(url, params=params, timeout=25)
    print(f"{name}: {r.json().get('count', 'error')}")
