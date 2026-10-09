import re

with open("permit_search_template.html", "r", encoding="utf-8") as f:
    html = f.read()

# Look for ng-messages, required, pattern, or min/max
validation_matches = re.findall(r'<[^>]+(?:required|ng-messages|data-val|pattern)[^>]*>', html)
for m in validation_matches:
    print("VALIDATOR:", m.strip()[:200])

# Look for all form controls and their attributes
inputs = re.findall(r'<input[^>]+>', html)
for inp in inputs:
    print("INPUT:", inp.strip())
