import json

with open("addison_permit_types.json", "r") as f:
    data = json.load(f)

print("Top level keys in Result:", data.keys())
statuses = data.get("PermitStatuses", []) or data.get("Statuses", [])
print("Statuses count:", len(statuses))
if statuses:
    print("Sample statuses:", json.dumps(statuses[:5], indent=2))
