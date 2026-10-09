import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US",
    "Referer": base_url,
}

with open("energov_criteria.json", "r") as f:
    template = json.load(f)["Result"]

template["Keyword"] = "roof"
template["ExactMatch"] = False
template["PageNumber"] = 1
template["PageSize"] = 50
template["SearchModule"] = 1
template["FilterModule"] = 1

search_url = f"{base_url}/api/energov/search/search"

client = httpx.Client(headers=headers, timeout=25.0, verify=False)
r = client.post(search_url, json=template)
print("HTTP Status:", r.status_code)
data = r.json()
print("Success:", data.get("Success"))
results = data.get("Result", {}).get("EntityResults", [])
print(f"EntityResults count: {len(results)}")
if results:
    print("First record:", results[0].get("CaseNumber"), results[0].get("CaseType"), results[0].get("Address", {}).get("FullAddress"))
