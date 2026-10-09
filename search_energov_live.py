import json
import httpx

with open("energov_criteria.json", "r") as f:
    data = json.load(f)

result = data["Result"]
print("Available criteria keys:", result.keys())
permit_criteria = result.get("PermitCriteria", {})
print("\nPermitCriteria template:")
print(json.dumps(permit_criteria, indent=2))

# Now test searching using the full Search criteria object or PermitCriteria object!
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

# Let's set search criteria
search_obj = result.copy()
search_obj["Keyword"] = "roof"
search_obj["PageNumber"] = 1
search_obj["PageSize"] = 25
search_obj["SearchModule"] = 1  # 1 = Permits / Plans

# Try POST to /api/energov/search/search with full search_obj
print("\n--- Trying POST /api/energov/search/search with criteria object ---")
try:
    r = client.post(f"{base_url}/api/energov/search/search", json=search_obj)
    print("Status:", r.status_code)
    res = r.json()
    print("Success:", res.get("Success"))
    print("TotalFound:", res.get("TotalFound"))
    if res.get("Result"):
        print("First result:", json.dumps(res["Result"][0], indent=2)[:500])
except Exception as e:
    print("Error:", e)

# Try POST to /api/energov/permits/search with PermitCriteria
permit_criteria["Description"] = "roof"
permit_criteria["PageNumber"] = 1
permit_criteria["PageSize"] = 25
print("\n--- Trying POST /api/energov/permits/search with PermitCriteria ---")
try:
    r = client.post(f"{base_url}/api/energov/permits/search", json=permit_criteria)
    print("Status:", r.status_code)
    res = r.json()
    print("Success:", res.get("Success"))
    print("TotalFound:", res.get("TotalFound"))
    if res.get("Result"):
        print("First permit result:", json.dumps(res["Result"][0], indent=2)[:500])
except Exception as e:
    print("Error:", e)
