import httpx
import json

client = httpx.Client(timeout=10.0)

# Check search for Addison
r = client.get("http://127.0.0.1:8000/api/v1/permits/search?jurisdiction=Addison")
print("Search Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print("Addison Permits Total:", data.get("total"))
    print("Addison Permits Count:", data.get("count"))
    if data.get("permits"):
        print("\nSample Addison Permit Record:")
        print(json.dumps(data["permits"][0], indent=2))

# Check overall warehouse stats
r_stats = client.get("http://127.0.0.1:8000/api/v1/permits/stats")
print("\nStats Status:", r_stats.status_code)
if r_stats.status_code == 200:
    s = r_stats.json()
    print("Total Ingested Permits Across Nation:", s.get("total_permits"))
    print("Total Valuation:", f"${s.get('total_valuation_usd'):,.2f}")
    print("Permits by Jurisdiction:", json.dumps(s.get("by_jurisdiction"), indent=2))
