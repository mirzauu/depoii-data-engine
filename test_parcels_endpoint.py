import httpx

def test_api():
    try:
        resp = httpx.get("http://127.0.0.1:8000/api/v1/parcels/tarrant?limit=3", timeout=20.0)
        print("Status code:", resp.status_code)
        data = resp.json()
        print("Source:", data.get("source"))
        print(f"Total: {data.get('total')}")
        for p in data.get("parcels", []):
            print(f"- {p['id']} | {p['address']}, {p['city']} | {p['building_sqft']:,} sqft | ${p['total_valuation']:,.0f}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_api()
