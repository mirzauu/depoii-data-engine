import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice/"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

r = client.get(base_url)
inline = re.findall(r'<script(?:\s+[^>]*)?>([\s\S]*?)</script>', r.text)
for i, s in enumerate(inline):
    if "globalsService" in s or "globals." in s:
        print(f"=== Script {i} ===")
        print(s)
