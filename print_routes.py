import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

b_url = base_url + "/app/energov?v=hBDuo8fiLeaZClnVFG_Kr_9VFupAHnm_kP-Fk_zXp6Q1"
text = client.get(b_url).text

for m in re.finditer(r'\.when\([\'"](/[a-zA-Z0-9_-]+)[\'"]', text):
    print("ROUTE:", m.group(1))
