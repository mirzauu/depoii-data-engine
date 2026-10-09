import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=25.0, headers={
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*"
})

urls = [
    f"{base_url}/api/tenants/gettenantslist",
    f"{base_url}/Home/GetTenants",
    f"{base_url}/tenants/gettenantslist",
]

for u in urls:
    try:
        r = client.get(u)
        print(f"GET {u} -> HTTP {r.status_code}")
        print("Body:", r.text[:500])
        print()
    except Exception as e:
        print(f"Error {u}: {e}")
