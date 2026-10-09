import httpx

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

urls = [
    f"{base_url}/EnerGovProd/EnergovSearch/search",
    f"{base_url}/EnergovSearch/search",
]

for u in urls:
    try:
        r = client.get(u)
        print(f"GET {u} -> HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            print("Preview of public search template:")
            print(r.text[:2000])
            with open("public_search_template.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            break
    except Exception as e:
        print(f"Error {u}: {e}")
