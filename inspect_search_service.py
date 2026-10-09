import httpx

base_url = "https://egov.addisontx.gov/energov_prod/selfservice"
client = httpx.Client(verify=False, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"})

b_url = base_url + "/app/energov?v=hBDuo8fiLeaZClnVFG_Kr_9VFupAHnm_kP-Fk_zXp6Q1"
text = client.get(b_url).text

idx = text.find('this.rootUrl="/energov/permits/search/"')
if idx != -1:
    print(text[max(0, idx - 100):min(len(text), idx + 800)])
