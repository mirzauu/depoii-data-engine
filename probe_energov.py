import httpx
import json

base_url = "https://egov.mckinneytexas.org/EnerGov_Prod/SelfService"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": "https://egov.mckinneytexas.org/EnerGov_Prod/SelfService"
}

client = httpx.Client(headers=headers, timeout=15.0, verify=False)

candidate_endpoints = [
    "/api/energov/search/search",
    "/api/energov/permit/search",
    "/api/energov/permits/search",
    "/api/selfservice/permitsearch",
    "/api/selfservice/systemsettings",
    "/api/energov/search/criteria",
    "/api/energov/search/types",
    "/api/energov/search/v1/search",
]

payloads = [
    {"keyword": "roof", "pageNumber": 1, "pageSize": 10},
    {"SearchText": "roof", "PageNumber": 1, "PageSize": 10},
    {"pageNumber": 1, "pageSize": 10, "sort": "", "filter": []},
]

print("--- Testing GET Requests ---")
for ep in candidate_endpoints:
    url = f"{base_url}{ep}"
    try:
        r = client.get(url)
        print(f"GET {ep} -> {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            print("Response preview:", r.text[:200])
    except Exception as e:
        print(f"GET {ep} -> Error: {e}")

print("\n--- Testing POST Requests ---")
for ep in candidate_endpoints:
    url = f"{base_url}{ep}"
    for i, p in enumerate(payloads):
        try:
            r = client.post(url, json=p)
            if r.status_code != 404:
                print(f"POST {ep} (p{i}) -> {r.status_code} ({len(r.text)} bytes)")
                if r.status_code == 200:
                    print("Response preview:", r.text[:300])
                    break
        except Exception as e:
            print(f"POST {ep} -> Error: {e}")
            break
