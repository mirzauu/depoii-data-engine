import httpx

url = "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/DallasTaxParcels/FeatureServer/0/query"
params = {
    "where": "ST_NAME LIKE '%COMMERCE%'",
    "resultRecordCount": 2,
    "outFields": "ACCT,TAXPANAME1,ST_NUM,ST_NAME,ST_TYPE,AREA_FEET,PROP_CL,Website",
    "f": "json"
}
r = httpx.get(url, params=params, timeout=15)
if r.status_code == 200:
    for f in r.json().get("features", []):
        print(f["attributes"])
