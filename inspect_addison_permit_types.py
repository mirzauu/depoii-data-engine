import httpx
import json

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "tenantId": "1",
    "tenantName": "EnerGovProd",
    "Tyler-TenantUrl": "EnerGovProd",
    "Tyler-Tenant-Culture": "en-US"
}

client = httpx.Client(headers=headers, timeout=30.0, verify=False)
r = client.get(f"{base_url}/api/energov/permits/search/setup")
data = r.json()

permit_types = data.get("Result", {}).get("PermitTypes", [])
print(f"Total Permit Types in Addison: {len(permit_types)}")

roof_matches = []
for pt in permit_types:
    p_name = pt.get("PermitTypeName", "")
    w_classes = pt.get("WorkClassTemplates", [])
    is_roof = "roof" in p_name.lower() or "commercial" in p_name.lower() or "building" in p_name.lower()
    for wc in w_classes:
        wc_name = wc.get("WorkclassName", "")
        if "roof" in wc_name.lower():
            is_roof = True
    if is_roof:
        roof_matches.append({
            "TypeId": pt.get("PermitTypeId"),
            "TypeName": p_name,
            "WorkClasses": [w.get("WorkclassName") for w in w_classes]
        })

print("\nRelevant Roofing/Commercial Permit Types:")
print(json.dumps(roof_matches[:10], indent=2))

with open("addison_permit_types.json", "w") as f:
    json.dump(data["Result"], f, indent=2)
