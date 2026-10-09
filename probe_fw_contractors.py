import httpx

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'
params = {
    'where': "Permit_Type = 'Commercial Building Permit' AND File_Date >= date '2026-01-01'",
    'resultRecordCount': 15,
    'outFields': 'Permit_No,B1_SPECIAL_TEXT,B1_WORK_DESC,Owner_Full_Name,JobValue',
    'f': 'json'
}
r = httpx.get(url, params=params, timeout=20)
for f in r.json().get('features', []):
    a = f['attributes']
    print(f"Permit: {a.get('Permit_No')} | Val: {a.get('JobValue')}")
    print(f"  Special: {a.get('B1_SPECIAL_TEXT')}")
    print(f"  Owner: {a.get('Owner_Full_Name')}")
    print(f"  Work: {str(a.get('B1_WORK_DESC'))[:80]}")
    print()
