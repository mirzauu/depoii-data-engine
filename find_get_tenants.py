import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

for b in ["/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1", "/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01"]:
    b_url = base_url + b
    text = client.get(b_url).text
    for match in re.finditer(r'getTenants\s*=', text):
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 300)
        print("FOUND in", b)
        print(text[start:end])
        print()
