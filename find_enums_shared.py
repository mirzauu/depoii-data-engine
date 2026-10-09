import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

for b in ["/selfservice/shared?v=rUm0eWuPp4Gm8gMcZ1QFGaN5cBC7dcxZd0Pykuwoid41", "/selfservice/core?v=NXtVrx5GBDZxdwxYWXaDsxhLBk1MvWcsv3Fvdddbs8A1"]:
    b_url = base_url + b
    text = client.get(b_url).text
    for m in re.finditer(r'SelfServiceModules\s*=\s*\{[^}]+\}', text):
        print("MATCH:", m.group(0))
