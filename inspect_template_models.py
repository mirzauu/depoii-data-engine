import re

with open("permit_search_template.html", "r", encoding="utf-8") as f:
    html = f.read()

models = re.findall(r'(?:ng-model|data-ng-model)=["\']([^"\']+)["\']', html)
print("All ng-model bindings:")
for m in sorted(set(models)):
    print(" -", m)

print("\n--- Form action & method ---")
form_match = re.search(r'<form[^>]+>', html)
if form_match:
    print(form_match.group(0))

print("\n--- All Input/Select Names and IDs ---")
inputs = re.findall(r'<(?:input|select)[^>]+(?:name|id)=["\']([^"\']+)["\']', html)
for inp in sorted(set(inputs)):
    print(" -", inp)
