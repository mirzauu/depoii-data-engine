import httpx

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'
params = {
    'where': "Permit_Type = 'Commercial Building Permit' AND File_Date >= date '2026-01-01'",
    'resultOffset': 0,
    'resultRecordCount': 5,
    'orderByFields': 'ObjectId ASC',
    'outFields': '*',
    'f': 'json'
}
r = httpx.get(url, params=params, timeout=20)
print('Status:', r.status_code)
features = r.json().get('features', [])
print('Count returned:', len(features))
if features:
    a = features[0]['attributes']
    print('First permit:', a.get('Permit_No'), '| Val:', a.get('JobValue'), '| Loc:', a.get('Location_1'), '| Date:', a.get('File_Date'))
