import json
import httpx

with open("energov_criteria.json", "r") as f:
    data = json.load(f)

result = data["Result"]

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

search_obj = result.copy()
search_obj["Keyword"] = "roof"
search_obj["PageNumber"] = 1
search_obj["PageSize"] = 10
search_obj["SearchModule"] = 1

r1 = client.post(f"{base_url}/api/energov/search/search", json=search_obj)
print("=== /api/energov/search/search Response ===")
print(r1.text)

permit_criteria = result.get("PermitCriteria", {})
permit_criteria["Description"] = "roof"
permit_criteria["EnableDescriptionSearch"] = True
permit_criteria["PageNumber"] = 1
permit_criteria["PageSize"] = 10

r2 = client.post(f"{base_url}/api/energov/permits/search", json=permit_criteria)
print("\n=== /api/energov/permits/search Response ===")
print(r2.text)
