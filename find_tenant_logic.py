import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

core_url = base_url + "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"
text = client.get(core_url).text

for match in re.finditer(r'Tyler-TenantUrl', text):
    start = max(0, match.start() - 200)
    end = min(len(text), match.end() + 200)
    print("--- SNIPPET AROUND Tyler-TenantUrl ---")
    print(text[start:end])
    print()

for match in re.finditer(r'tenantId', text, re.IGNORECASE):
    start = max(0, match.start() - 150)
    end = min(len(text), match.end() + 150)
    print("--- SNIPPET AROUND tenantId ---")
    print(text[start:end])
    print()
