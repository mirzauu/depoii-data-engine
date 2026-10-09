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

client = httpx.Client(headers=headers, timeout=25.0, verify=False)
r = client.get(f"{base_url}/api/Home/Menu")
data = r.json()

menus = data.get("Result", {}).get("Menus", [])
print(f"Found {len(menus)} top-level menus:")
for m in menus:
    print(f" - [{m.get('MenuID')}] {m.get('Label')}: Route -> {m.get('Route')}")
    for sm in m.get("SubMenus", []):
        print(f"     * [{sm.get('MenuID')}] {sm.get('Label')}: Route -> {sm.get('Route')}")

with open("addison_menus.json", "w") as f:
    json.dump(data, f, indent=2)
