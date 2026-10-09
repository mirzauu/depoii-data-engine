import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": "https://egov.addisontx.gov/energov_prod/selfservice"
}

client = httpx.Client(headers=headers, timeout=12.0, verify=False)

candidate_endpoints = [
    "",
    "/api/energov/search/search",
    "/api/energov/permit/search",
    "/api/energov/permits/search",
    "/api/selfservice/permitsearch",
    "/api/selfservice/systemsettings",
    "/api/energov/search/criteria",
    "/api/energov/search/types",
    "/api/energov/search/v1/search",
    "/api/selfservice/search/search",
    "/api/EnerGov/Search/AdvancedSearch"
]

print("--- Testing GET Requests on Town of Addison EnerGov CSS ---")
for ep in candidate_endpoints:
    url = f"{base_url}{ep}"
    try:
        r = client.get(url)
        print(f"GET {ep or '/'} -> HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            print("Preview:", r.text[:200].replace('\n', ' '))
    except Exception as e:
        print(f"GET {ep or '/'} -> Error: {e}")

payload = {
    "keyword": "roof",
    "pageNumber": 1,
    "pageSize": 10
}

print("\n--- Testing POST Requests ---")
for ep in candidate_endpoints[1:]:
    url = f"{base_url}{ep}"
    try:
        r = client.post(url, json=payload)
        print(f"POST {ep} -> HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            print("Response preview:", r.text[:300].replace('\n', ' '))
    except Exception as e:
        print(f"POST {ep} -> Error: {e}")
