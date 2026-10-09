import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": "https://egov.addisontx.gov/energov_prod/selfservice",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US"
}

client = httpx.Client(headers=headers, timeout=30.0, verify=False)

variations = [
    # 1. Blank search (get all recent permits)
    {"name": "Blank search", "payload": {
        "Address": "", "PermitNumber": "", "ProjectName": "", "PMPermitTypeId": "",
        "PMPermitWorkClassId": "", "PMPermitStatusId": "", "StartIssueDate": None, "EndIssueDate": None,
        "StartExpirationDate": None, "EndExpirationDate": None, "StartFinaledDate": None, "EndFinaledDate": None,
        "SearchMyPermitsOnly": False, "PageNumber": 1, "PageSize": 10
    }},
    # 2. Search by Address 'Belt Line' (Addison's main commercial artery)
    {"name": "Address Belt Line", "payload": {
        "Address": "Belt Line", "PermitNumber": "", "ProjectName": "", "PMPermitTypeId": "",
        "PMPermitWorkClassId": "", "PMPermitStatusId": "", "StartIssueDate": None, "EndIssueDate": None,
        "StartExpirationDate": None, "EndExpirationDate": None, "StartFinaledDate": None, "EndFinaledDate": None,
        "SearchMyPermitsOnly": False, "PageNumber": 1, "PageSize": 10
    }},
    # 3. Search by Address 'Midway'
    {"name": "Address Midway", "payload": {
        "Address": "Midway", "PermitNumber": "", "ProjectName": "", "PMPermitTypeId": "",
        "PMPermitWorkClassId": "", "PMPermitStatusId": "", "StartIssueDate": None, "EndIssueDate": None,
        "StartExpirationDate": None, "EndExpirationDate": None, "StartFinaledDate": None, "EndFinaledDate": None,
        "SearchMyPermitsOnly": False, "PageNumber": 1, "PageSize": 10
    }},
    # 4. Search Roof with null dates
    {"name": "Roof null dates", "payload": {
        "Address": "", "PermitNumber": "", "ProjectName": "", "PMPermitTypeId": "aac3a6ef-eabe-428c-b996-2a0615c388fa",
        "PMPermitWorkClassId": "", "PMPermitStatusId": "", "StartIssueDate": None, "EndIssueDate": None,
        "StartExpirationDate": None, "EndExpirationDate": None, "StartFinaledDate": None, "EndFinaledDate": None,
        "SearchMyPermitsOnly": False, "PageNumber": 1, "PageSize": 10
    }},
    # 5. Commercial Building Permits
    {"name": "Commercial Building Permits", "payload": {
        "Address": "", "PermitNumber": "", "ProjectName": "", "PMPermitTypeId": "0ca907c8-392e-4220-abb0-c3c99089c544",
        "PMPermitWorkClassId": "", "PMPermitStatusId": "", "StartIssueDate": None, "EndIssueDate": None,
        "StartExpirationDate": None, "EndExpirationDate": None, "StartFinaledDate": None, "EndFinaledDate": None,
        "SearchMyPermitsOnly": False, "PageNumber": 1, "PageSize": 10
    }}
]

url = f"{base_url}/api/energov/permits/search"

for v in variations:
    try:
        r = client.post(url, json=v["payload"])
        data = r.json()
        print(f"[{v['name']}] -> TotalFound: {data.get('TotalFound')}, Success: {data.get('Success')}")
        if data.get("Result"):
            print(f">>> BINGO! Found {len(data['Result'])} records! <<<")
            print("First item preview:")
            print(json.dumps(data["Result"][0], indent=2))
            with open("addison_permit_record.json", "w") as f:
                json.dump(data["Result"], f, indent=2)
            break
    except Exception as e:
        print(f"Error {v['name']}: {e}")
