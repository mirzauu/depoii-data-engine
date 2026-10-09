import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US"
}

client = httpx.Client(headers=headers, timeout=25.0, verify=False)
r = client.get(f"{base_url}/api/energov/search/criteria")
criteria = r.json()

print(json.dumps(criteria, indent=2))

with open("energov_criteria.json", "w") as f:
    json.dump(criteria, f, indent=2)
