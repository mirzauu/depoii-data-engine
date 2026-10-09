import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

for b in ["/app/energov?v=hBDuo8fiLeaZClnVFG_Kr_9VFupAHnm_kP-Fk_zXp6Q1", "/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01"]:
    b_url = base_url + b
    text = client.get(b_url).text
    for m in re.finditer(r'\.when\([\'"][^\'"]*search[^\'"]*[\'"]', text, re.IGNORECASE):
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 300)
        print("ROUTE MATCH in", b)
        print(text[start:end])
        print()
