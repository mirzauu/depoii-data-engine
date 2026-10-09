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

# Let's test with Roof permit type: aac3a6ef-eabe-428c-b996-2a0615c388fa
payload = {
    "Address": "",
    "PermitNumber": "",
    "ProjectName": "",
    "PMPermitTypeId": "aac3a6ef-eabe-428c-b996-2a0615c388fa", # Roof
    "PMPermitWorkClassId": "",
    "PMPermitStatusId": "",
    "StartIssueDate": "2023-01-01T00:00:00.000Z",
    "EndIssueDate": "2026-10-06T00:00:00.000Z",
    "StartExpirationDate": None,
    "EndExpirationDate": None,
    "StartFinaledDate": None,
    "EndFinaledDate": None,
    "SearchMyPermitsOnly": False,
    "PageNumber": 1,
    "PageSize": 25,
    "SortBy": "IssueDate",
    "SortAscending": False
}

urls = [
    f"{base_url}/api/energov/permits/search",
    f"{base_url}/api/energov/permits/search/",
]

for u in urls:
    try:
        r = client.post(u, json=payload)
        print(f"POST {u} -> HTTP {r.status_code}")
        res = r.json()
        print("Success:", res.get("Success"))
        print("TotalFound:", res.get("TotalFound"))
        print("PageCount:", res.get("PageCount"))
        print("StatusCode:", res.get("StatusCode"))
        if res.get("Result"):
            print(f">>> FOUND {len(res['Result'])} PERMITS! <<<")
            print("First permit sample:")
            print(json.dumps(res["Result"][0], indent=2))
            with open("sample_energov_permit.json", "w") as f:
                json.dump(res["Result"], f, indent=2)
            break
        else:
            print("Response:", json.dumps(res, indent=2)[:500])
    except Exception as e:
        print(f"Error {u}: {e}")
