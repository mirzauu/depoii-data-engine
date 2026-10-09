import httpx
import json

url = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"
params = {
    "where": "SITUS_ADDR LIKE '%COMMERCE%'",
    "resultRecordCount": 2,
    "outFields": "SITUS_ADDR,ACCOUNT,OWNER_NAME,TOTAL_VALU",
    "f": "json"
}
r = httpx.get(url, params=params, timeout=15)
if r.status_code == 200:
    for f in r.json().get("features", []):
        print(f["attributes"])
