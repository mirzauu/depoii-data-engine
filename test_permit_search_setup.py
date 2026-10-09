import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": "https://egov.addisontx.gov/energov_prod/selfservice",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US"
}

client = httpx.Client(headers=headers, timeout=30.0, verify=False)

eps = [
    "/api/energov/permits/search/criteria",
    "/api/energov/permits/search/setup",
]

for ep in eps:
    r = client.get(f"{base_url}{ep}")
    print(f"GET {ep} -> {r.status_code}")
    print(r.text[:600])
    print()

# Now test POST /api/energov/permits/search/ with the permit criteria
r_crit = client.get(f"{base_url}/api/energov/permits/search/criteria")
if r_crit.status_code == 200:
    crit = r_crit.json().get("Result", {})
    crit["Description"] = "roof"
    crit["PageNumber"] = 1
    crit["PageSize"] = 10
    
    print("\nTesting POST /api/energov/permits/search/ with criteria:")
    r_post = client.post(f"{base_url}/api/energov/permits/search/", json=crit)
    print("POST status:", r_post.status_code)
    print(r_post.text[:1000])
