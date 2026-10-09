import httpx
import json

def test_nyc_pluto():
    print("--- Testing NYC MapPLUTO ---")
    url = "https://data.cityofnewyork.us/resource/64uk-42ks.json"
    params = {
        "$limit": 3,
        "$select": "bbl,address,ownername,bldgclass,bldgarea,yearbuilt,lotarea,assessval,latitude,longitude"
    }
    try:
        r = httpx.get(url, params=params, timeout=15)
        print("NYC Pluto Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("Sample NYC Pluto Record:", json.dumps(data[0] if data else {}, indent=2))
            return True
    except Exception as e:
        print("NYC Pluto error:", e)
    return False

def test_dallas_parcels():
    print("\n--- Testing Dallas GIS Parcels ---")
    # City of Dallas GIS Parcels
    candidate_urls = [
        "https://gis.dallascityhall.com/arcgis/rest/services/OpenData/OpenData/MapServer/2/query",
        "https://services.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/DCAD_Parcels/FeatureServer/0/query",
        "https://gis.dallascityhall.com/arcgis/rest/services/Dallas_Property/MapServer/0/query",
    ]
    for u in candidate_urls:
        try:
            r = httpx.get(u, params={"where": "1=1", "resultRecordCount": 1, "outFields": "*", "f": "json"}, timeout=10)
            print(f"URL: {u} -> Status: {r.status_code}")
            if r.status_code == 200 and "features" in r.json():
                feat = r.json()["features"]
                if feat:
                    print("Sample Dallas Parcel:", json.dumps(feat[0]["attributes"], indent=2))
                    return u
        except Exception as e:
            print(f"Error {u}:", e)
    return None

def test_tarrant_parcels():
    print("\n--- Testing Tarrant TAD Parcels ---")
    url = "https://mapit.tarrantcounty.com/arcgis/rest/services/Tax/TCProperty/MapServer/0/query"
    try:
        r = httpx.get(url, params={"where": "1=1", "resultRecordCount": 1, "outFields": "*", "f": "json"}, timeout=15)
        print("Tarrant TAD Status:", r.status_code)
        if r.status_code == 200 and "features" in r.json():
            feat = r.json()["features"]
            if feat:
                print("Sample Tarrant Parcel:", json.dumps(feat[0]["attributes"], indent=2))
                return True
    except Exception as e:
        print("Tarrant TAD error:", e)
    return False

if __name__ == "__main__":
    nyc_ok = test_nyc_pluto()
    dal_url = test_dallas_parcels()
    tarrant_ok = test_tarrant_parcels()
    print("\nResults:", {"nyc_ok": nyc_ok, "dallas_url": dal_url, "tarrant_ok": tarrant_ok})
