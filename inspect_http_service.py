import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

core_url = base_url + "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"
text = client.get(core_url).text

idx = text.find('service("http",')
if idx == -1:
    idx = text.find('.service("http"')
if idx == -1:
    idx = text.find('factory("http"')
if idx != -1:
    print(text[idx - 100:idx + 600])
else:
    # search for prototype.get=
    for m in re.finditer(r'prototype\.get\s*=', text):
        print(text[m.start() - 100:m.end() + 300])
