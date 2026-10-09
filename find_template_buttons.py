import re

with open("permit_search_template.html", "r", encoding="utf-8") as f:
    html = f.read()

buttons = re.findall(r'<button[^>]*>[\s\S]*?</button>', html)
for b in buttons:
    print("BUTTON:", b.strip()[:300])
    print()
