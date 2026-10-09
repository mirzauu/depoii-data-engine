import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

core_url = base_url + "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"
text = client.get(core_url).text

for match in re.finditer(r'tenantId\s*=', text, re.IGNORECASE):
    print("MATCH =", text[max(0, match.start() - 100):min(len(text), match.end() + 100)])

# Also search app/modules and app/energov bundles
for b in ["/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01", "/app/energov?v=hBDuo8fiLeaZClnVFG_Kr_9VFupAHnm_kP-Fk_zXp6Q1"]:
    b_url = base_url + b
    b_text = client.get(b_url).text
    print(f"\nChecking bundle {b} (len={len(b_text)})")
    for match in re.finditer(r'tenantId\s*=', b_text, re.IGNORECASE):
        print("MATCH in bundle =", b_text[max(0, match.start() - 100):min(len(text), match.end() + 100)])
    for match in re.finditer(r'tenantName\s*=', b_text, re.IGNORECASE):
        print("MATCH tenantName in bundle =", b_text[max(0, match.start() - 100):min(len(text), match.end() + 100)])
