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

client = httpx.Client(headers=headers, timeout=25.0, verify=False)
search_url = f"{base_url}/api/energov/permits/search/"

# Load permit types
with open("addison_permit_types.json", "r") as f:
    setup_data = json.load(f)

permit_types = setup_data.get("PermitTypes", [])

# Let's test searching with different criteria
test_cases = [
    {"name": "No Type (All Recent Permits)", "payload": {"PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}},
    {"name": "Address 'Belt Line'", "payload": {"Address": "Belt Line", "PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}},
    {"name": "Address 'Midway'", "payload": {"Address": "Midway", "PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}},
    {"name": "Address 'Airport'", "payload": {"Address": "Airport", "PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}},
    {"name": "Address 'Dallas'", "payload": {"Address": "Dallas", "PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}},
]

# Add top 10 permit types
for pt in permit_types[:10]:
    t_id = pt.get("PermitTypeId")
    t_name = pt.get("PermitTypeName")
    if t_id and t_name:
        test_cases.append({
            "name": f"Type: {t_name}",
            "payload": {"PMPermitTypeId": t_id, "PageNumber": 1, "PageSize": 25, "SearchMyPermitsOnly": False}
        })

print(f"Testing {len(test_cases)} query variations directly via httpx...")

for tc in test_cases:
    try:
        r = client.post(search_url, json=tc["payload"])
        data = r.json()
        total = data.get("TotalFound", 0)
        success = data.get("Success", False)
        print(f"[{tc['name']}] -> TotalFound: {total}, Success: {success}")
        if data.get("Result") and len(data["Result"]) > 0:
            print(f">>> FOUND {len(data['Result'])} PERMIT RECORDS! <<<")
            print("First permit:")
            print(json.dumps(data["Result"][0], indent=2))
            with open("addison_permits_harvested.json", "w") as f:
                json.dump(data["Result"], f, indent=2)
            break
    except Exception as e:
        print(f"Error {tc['name']}: {e}")
