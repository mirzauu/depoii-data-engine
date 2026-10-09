import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

core_url = base_url + "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"
r = client.get(core_url)
print("Core bundle size:", len(r.text))

# Search for headers set in core
header_matches = re.findall(r'headers\[[\'"][^\'"]+[\'"]\]', r.text)
print("Headers set:", set(header_matches))

tenant_matches = re.findall(r'[\w\.-]*tenant[\w\.-]*', r.text, re.IGNORECASE)
print("Tenant occurrences:", set(tenant_matches[:30]))

# Search for search service or permit search URL
apis = re.findall(r'/api/energov/[a-zA-Z0-9/_-]+', r.text)
print("APIs referenced in core:", set(apis))
