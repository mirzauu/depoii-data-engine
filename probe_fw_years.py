import httpx

url = 'https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/CFW_Open_Data_Development_Permits_View/FeatureServer/0/query'

for yr in ['2024', '2025', '2026']:
    start = f"{yr}-01-01"
    end = f"{int(yr)+1}-01-01" if yr != '2026' else '2027-01-01'
    w = f"Permit_Type = 'Commercial Building Permit' AND File_Date >= date '{start}' AND File_Date < date '{end}'"
    r = httpx.get(url, params={'where': w, 'returnCountOnly': 'true', 'f': 'json'}, timeout=15)
    print(f"Year {yr}: {r.json().get('count')}")
