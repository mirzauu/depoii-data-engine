import httpx
import re

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, follow_redirects=True, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
})

r = client.get(base_url + "/")
print("HTML length:", len(r.text))

# Search for scripts
matches = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
print("Scripts found:", matches)

# Check inline scripts
inline = re.findall(r'<script(?:\s+[^>]*)?>([\s\S]*?)</script>', r.text)
for i, s in enumerate(inline):
    if s.strip():
        print(f"--- Inline script {i} ---")
        print(s.strip()[:600])

# Look for tenant in HTML
for line in r.text.splitlines():
    if "tenant" in line.lower() or "energov" in line.lower() or "api" in line.lower():
        print("MATCHING LINE:", line.strip()[:200])
