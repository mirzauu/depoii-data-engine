import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US"
}

client = httpx.Client(headers=headers, timeout=30.0, verify=False)

urls = [
    f"{base_url}/api/energov/dashboard/permits",
    f"{base_url}/api/energov/dashboard/permits/",
]

payloads = [
    None,
    {},
    {"Keyword": "roof", "PageNumber": 1, "PageSize": 10},
    {"StatusOption": 1, "PageNumber": 1, "PageSize": 25, "Keyword": "", "ModuleId": 1}
]

for url in urls:
    for i, p in enumerate(payloads):
        try:
            r = client.post(url, json=p)
            print(f"POST {url} (p{i}) -> HTTP {r.status_code}")
            print(r.text[:600])
            print("-" * 50)
        except Exception as e:
            print(f"Error {url} p{i}: {e}")
