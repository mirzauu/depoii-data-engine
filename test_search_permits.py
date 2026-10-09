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

# Let's inspect search criteria or query permits
payloads = [
    {"Keyword": "roof", "PageNumber": 1, "PageSize": 20, "SortBy": "IssueDate", "SortAscending": False},
    {"keyword": "roof", "pageNumber": 1, "pageSize": 20},
    {"SearchText": "roof", "PageNumber": 1, "PageSize": 20},
    {"PermitNumber": "", "Keyword": "roof", "PageNumber": 1, "PageSize": 20},
]

endpoints = [
    "/api/energov/permits/search",
    "/api/energov/search/search",
]

for ep in endpoints:
    url = f"{base_url}{ep}"
    for i, p in enumerate(payloads):
        try:
            r = client.post(url, json=p)
            print(f"POST {ep} (payload {i}) -> HTTP {r.status_code}")
            data = r.json()
            print("Response:", json.dumps(data, indent=2)[:800])
            if data.get("Success") or data.get("TotalFound", 0) > 0:
                print(">>> SUCCESSFUL SEARCH! <<<")
                break
        except Exception as e:
            print(f"Error {ep} payload {i}: {e}")
