import httpx

def search_fw():
    params = {
        "q": '("Fort Worth" OR "CFW") AND (permit OR permits) AND type:"Feature Service"',
        "f": "json",
        "num": 15
    }
    r = httpx.get("https://www.arcgis.com/sharing/rest/search", params=params, timeout=15)
    print("Status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        for item in data.get("results", []):
            print(f"- Title: {item.get('title')}")
            print(f"  Owner: {item.get('owner')}")
            print(f"  URL: {item.get('url')}")
            print(f"  Type: {item.get('type')}")
            print()

if __name__ == "__main__":
    search_fw()
