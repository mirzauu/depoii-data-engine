import httpx
import json

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'
params = {
    'where': "Permit_Type = 'Commercial Building Permit' AND File_Date >= date '2026-01-01'",
    'resultRecordCount': 5,
    'orderByFields': 'File_Date DESC',
    'outFields': 'Permit_No,Permit_Type,Permit_SubType,B1_SPECIAL_TEXT,B1_WORK_DESC,Full_Street_Address,Addr_No,Street_Name,Street_Suffix,Zip_Code,JobValue,Location_1,File_Date,Current_Status',
    'f': 'json'
}
r = httpx.get(url, params=params, timeout=20)
if r.status_code == 200:
    for f in r.json().get('features', []):
        print(json.dumps(f['attributes'], indent=2))
