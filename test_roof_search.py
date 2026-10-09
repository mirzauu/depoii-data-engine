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

permit_criteria = {
    "PermitNumber": None,
    "PermitTypeId": "aac3a6ef-eabe-428c-b996-2a0615c388fa",  # Roof
    "PermitWorkclassId": None,
    "PermitStatusId": None,
    "ProjectName": None,
    "IssueDateFrom": None,
    "IssueDateTo": None,
    "Address": None,
    "Description": None,
    "ExpireDateFrom": None,
    "ExpireDateTo": None,
    "FinalDateFrom": None,
    "FinalDateTo": None,
    "ApplyDateFrom": None,
    "ApplyDateTo": None,
    "SearchMainAddress": False,
    "ContactId": None,
    "TypeId": None,
    "WorkClassIds": None,
    "ParcelNumber": None,
    "ExcludeCases": None,
    "EnableDescriptionSearch": False,
    "PageNumber": 1,
    "PageSize": 10,
    "SortBy": "IssueDate",
    "SortAscending": False
}

urls_to_test = [
    f"{base_url}/api/energov/permits/search",
    f"{base_url}/api/energov/permits/search/",
    f"{base_url}/api/energov/search/search",
    f"{base_url}/api/energov/entity/permits/search/search"
]

for url in urls_to_test:
    try:
        r = client.post(url, json=permit_criteria)
        print(f"POST {url} -> HTTP {r.status_code}")
        print(r.text[:800])
        print("="*60)
    except Exception as e:
        print(f"Error {url}: {e}")
