import httpx

params = {
    "q": '("Dallas" OR "DCAD") AND (parcel OR parcels) AND type:"Feature Service"',
    "f": "json",
    "num": 10
}
r = httpx.get("https://www.arcgis.com/sharing/rest/search", params=params, timeout=15)
if r.status_code == 200:
    for item in r.json().get("results", []):
        print(f"- {item.get('title')} | Owner: {item.get('owner')}")
        print(f"  URL: {item.get('url')}\n")
