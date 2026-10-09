import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

b_url = base_url + "/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01"
text = client.get(b_url).text

for match in re.finditer(r'processMultiTenants', text):
    start = max(0, match.start() - 300)
    end = min(len(text), match.end() + 300)
    print("--- CALL TO processMultiTenants ---")
    print(text[start:end])
    print()
