import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

b_url = base_url + "/app/modules?v=WRW0R8MDkKdfKs934wka1eeydR6r49QTotmxeKjq_m01"
text = client.get(b_url).text

idx = text.find('.when("/permits"')
if idx == -1:
    idx = text.find('.when(\'/permits\'')
print(text[idx - 50:idx + 500])
