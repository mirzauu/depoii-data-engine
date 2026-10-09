import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0"
})

b_url = base_url + "/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01"
text = client.get(b_url).text

idx = text.find('n.tenantId=i[0].TenantID')
if idx != -1:
    print(text[max(0, idx - 500):idx + 300])
