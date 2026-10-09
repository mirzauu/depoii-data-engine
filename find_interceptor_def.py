import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

core_url = base_url + "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"
text = client.get(core_url).text

idx = text.find('r.tenantId&&(n.headers.tenantId=r.tenantId)')
if idx != -1:
    print(text[max(0, idx - 400):idx + 300])
