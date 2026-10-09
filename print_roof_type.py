import json

with open("addison_permit_types.json", "r") as f:
    data = json.load(f)

for pt in data.get("PermitTypes", []):
    if pt.get("PermitTypeName") == "Roof":
        print(json.dumps(pt, indent=2))
