import httpx
import json

BASE_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

params = {
    "where": "1=1",
    "outFields": "*",
    "resultRecordCount": "2",
    "f": "json",
    "returnGeometry": "true",
    "outSR": "4326"
}

def explore():
    print(f"Connecting to: {BASE_URL}...")
    try:
        with httpx.Client(timeout=30.0, verify=False) as client:
            resp = client.get(BASE_URL, params=params, headers=headers)
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    print("ArcGIS Error:", data["error"])
                    return
                print("Fields available:")
                for f in data.get("fields", []):
                    print(f" - {f.get('name')} ({f.get('type')}, alias: {f.get('alias')})")
                
                features = data.get("features", [])
                print(f"\nFetched {len(features)} sample feature(s):")
                for idx, feat in enumerate(features):
                    print(f"\n--- Feature {idx + 1} ---")
                    print("Attributes:")
                    print(json.dumps(feat.get("attributes", {}), indent=2))
                    geom = feat.get("geometry", {})
                    print("Geometry keys:", list(geom.keys()))
            else:
                print(f"Error response: {resp.text[:500]}")
    except Exception as e:
        print(f"Exception during request: {e}")

if __name__ == "__main__":
    explore()
