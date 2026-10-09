import httpx
import json

BASE_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# Let's query high-value / large commercial buildings in Fort Worth or Tarrant County:
# e.g. LIVING_ARE > 40000 and TOTAL_VALU > 1000000
params = {
    "where": "LIVING_ARE > 40000 AND TOTAL_VALU > 1000000",
    "outFields": "OBJECTID,ACCOUNT,TAXPIN,OWNER_NAME,SITUS_ADDR,CITY,ZIPCODE,YEAR_BUILT,LIVING_ARE,TOTAL_VALU,PARCELTYPE,DESCR",
    "resultRecordCount": "5",
    "f": "json",
    "returnGeometry": "true",
    "outSR": "4326"
}

def test_commercial():
    with httpx.Client(timeout=30.0, verify=False) as client:
        resp = client.get(BASE_URL, params=params, headers=headers)
        data = resp.json()
        features = data.get("features", [])
        print(f"Found {len(features)} matching commercial/large properties:")
        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})
            rings = geom.get("rings", [])
            # Calculate simple centroid
            all_pts = [pt for ring in rings for pt in ring]
            if all_pts:
                avg_lon = sum(p[0] for p in all_pts) / len(all_pts)
                avg_lat = sum(p[1] for p in all_pts) / len(all_pts)
            else:
                avg_lon, avg_lat = None, None
            print(f"- [{attrs.get('ACCOUNT')}] {attrs.get('SITUS_ADDR').strip()}, {attrs.get('CITY').strip()} | Owner: {attrs.get('OWNER_NAME').strip()} | Sqft: {attrs.get('LIVING_ARE')} | Val: ${attrs.get('TOTAL_VALU'):,.0f} | Centroid: ({avg_lat:.4f}, {avg_lon:.4f})")

if __name__ == "__main__":
    test_commercial()
