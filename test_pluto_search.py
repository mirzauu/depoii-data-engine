import httpx

url = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query"
params = {
    "where": "Address LIKE '%BROADWAY%'",
    "resultRecordCount": 2,
    "outFields": "BBL,Address,OwnerName,BldgArea,LotArea,AssessTot,YearBuilt,ZipCode",
    "f": "json"
}
r = httpx.get(url, params=params, timeout=15)
if r.status_code == 200:
    for f in r.json().get("features", []):
        print(f["attributes"])
