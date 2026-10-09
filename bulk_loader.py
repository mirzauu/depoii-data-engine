import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.science.normalizer import batch_normalize_permits
from app.science.deduplicator import deduplicate_permits_in_memory
from app.api.v1.permits import _PERMIT_WAREHOUSE
from app.core.logging import logger

METRO_CONFIGS = [
    {
        "city_key": "chicago_il",
        "jurisdiction": "Chicago, IL",
        "state": "IL",
        "url": "https://data.cityofchicago.org/resource/ydr8-5enu.json",
        "description_field": "work_description",
        "roof_filter": True,
    },
    {
        "city_key": "cambridge_ma",
        "jurisdiction": "Cambridge, MA",
        "state": "MA",
        "url": "https://data.cambridgema.gov/resource/79ih-g44d.json",
        "description_field": "proposed_work_description",
        "roof_filter": False,
    },
    {
        "city_key": "cincinnati_oh",
        "jurisdiction": "Cincinnati, OH",
        "state": "OH",
        "url": "https://data.cincinnati-oh.gov/resource/uhjb-xac9.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "baton_rouge_la",
        "jurisdiction": "Baton Rouge, LA",
        "state": "LA",
        "url": "https://data.brla.gov/resource/7fq7-8j7r.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "seattle_wa",
        "jurisdiction": "Seattle, WA",
        "state": "WA",
        "url": "https://cos-data.seattle.gov/resource/76t5-zqzr.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "new_york_ny",
        "jurisdiction": "New York City, NY",
        "state": "NY",
        "url": "https://data.cityofnewyork.us/resource/rbx6-tga4.json",
        "description_field": "job_description",
        "roof_filter": False,
    },
    {
        "city_key": "montgomery_md",
        "jurisdiction": "Montgomery County, MD",
        "state": "MD",
        "url": "https://data.montgomerycountymd.gov/resource/i26v-w6bd.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "sonoma_ca",
        "jurisdiction": "Sonoma County, CA",
        "state": "CA",
        "url": "https://data.sonomacounty.ca.gov/resource/88ms-k5e7.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "framingham_ma",
        "jurisdiction": "Framingham, MA",
        "state": "MA",
        "url": "https://data.framinghamma.gov/resource/2vzw-yean.json",
        "description_field": "description",
        "roof_filter": False,
    },
    {
        "city_key": "gainesville_fl",
        "jurisdiction": "Gainesville, FL",
        "state": "FL",
        "url": "https://data.cityofgainesville.org/resource/p798-x3nx.json",
        "description_field": "job_description",
        "roof_filter": False,
    },
]

TIER3_ENERGOV_CONFIGS = [
    {
        "city_key": "addison_tx",
        "jurisdiction": "Addison, TX",
        "state": "TX",
        "base_url": "https://egov.addisontx.gov/energov_prod/selfservice",
        "tenant_id": "1",
        "tenant_name": "EnerGovProd",
        "tenant_url": "EnerGovProd",
        "culture": "en-US",
        "keywords": ["roof", "re-roof", "commercial", "tpo"],
    }
]

async def harvest_energov_metro(client: httpx.AsyncClient, config: dict) -> List[Dict[str, Any]]:
    """
    Harvests commercial roofing permits from a Tier 3 Tyler EnerGov / CSS municipality.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "tenantId": config["tenant_id"],
        "tenantName": config["tenant_name"],
        "Tyler-TenantUrl": config["tenant_url"],
        "Tyler-Tenant-Culture": config["culture"],
        "Referer": config["base_url"],
    }
    
    # 1. Fetch base criteria template
    crit_url = f"{config['base_url']}/api/energov/search/criteria"
    try:
        crit_res = await client.get(crit_url, headers=headers, timeout=20.0)
        base_template = crit_res.json().get("Result", {}) if crit_res.status_code == 200 else {}
    except Exception as e:
        print(f"[{config['jurisdiction']}] Failed to fetch criteria template: {e}")
        base_template = {}

    search_url = f"{config['base_url']}/api/energov/search/search"
    all_records = []
    seen_ids = set()

    for kw in config.get("keywords", ["roof"]):
        for page in range(1, 6):
            payload = base_template.copy() if base_template else {}
            payload["Keyword"] = kw
            payload["ExactMatch"] = False
            payload["SearchModule"] = 1
            payload["FilterModule"] = 1
            payload["SearchMainAddress"] = False
            payload["PageNumber"] = page
            payload["PageSize"] = 50
            payload["SortAscending"] = True

            try:
                res = await client.post(search_url, json=payload, headers=headers, timeout=25.0)
                if res.status_code != 200:
                    break
                data = res.json()
                results = data.get("Result", {}).get("EntityResults", [])
                if not results:
                    break
                for item in results:
                    cid = item.get("CaseId") or item.get("CaseNumber")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_records.append(item)
                if len(results) < 50:
                    break
            except Exception as e:
                print(f"[{config['jurisdiction']}] EnerGov error for kw '{kw}' page {page}: {e}")
                break

    print(f"[{config['jurisdiction']}] Harvested {len(all_records)} unique Tyler EnerGov permit cases")
    return all_records

async def harvest_metro(client: httpx.AsyncClient, metro: dict) -> List[Dict[str, Any]]:
    headers = {"User-Agent": "DepoiiDataEngine/2.0 (+https://depoii.com)"}
    try:
        res = await client.get(metro["url"], headers=headers, timeout=15.0)
        if res.status_code != 200:
            print(f"[{metro['jurisdiction']}] HTTP Error {res.status_code}")
            return []
        data = res.json()
        print(f"[{metro['jurisdiction']}] Downloaded {len(data)} raw permits from {metro['url']}")
        
        # If metro requires filtering, extract roofing-related permits
        if metro.get("roof_filter"):
            filtered = [
                d for d in data 
                if "roof" in (d.get("work_description") or "").lower() 
                or "roof" in (d.get("permit_type") or "").lower()
            ]
            print(f"[{metro['jurisdiction']}] Filtered down to {len(filtered)} commercial roofing permits")
            return filtered
        return data
    except Exception as e:
        print(f"[{metro['jurisdiction']}] Exception: {e}")
        return []

async def run_bulk_ingest():
    print("==================================================")
    print("  DEPOII NATIONAL BULK INGESTION RUNNER           ")
    print("==================================================")
    
    total_raw = 0
    total_normalized = 0
    total_duplicates_removed = 0
    
    async with httpx.AsyncClient(timeout=25.0) as client:
        # 1. Harvest Tier 1 Socrata Open Data Metros
        for metro in METRO_CONFIGS:
            raw_records = await harvest_metro(client, metro)
            if not raw_records:
                continue
            
            total_raw += len(raw_records)
            
            # Map metro-specific fields for maximum normalization accuracy
            if metro["city_key"] == "cambridge_ma":
                for r in raw_records:
                    r["contractor_name"] = r.get("firm_name") or r.get("applicant_name")
                    r["estimated_cost"] = r.get("building_cost")
                    r["street_address"] = r.get("full_address")
                    r["work_description"] = r.get("proposed_work_description") or r.get("roof_work_description")
            elif metro["city_key"] == "new_york_ny":
                for r in raw_records:
                    r["permit_number"] = r.get("job_filing_number") or r.get("bin")
                    r["contractor_name"] = r.get("applicant_business_name") or r.get("general_contractor_business_name")
                    r["estimated_cost"] = r.get("estimated_job_costs") or r.get("initial_cost")
                    r["street_address"] = f"{r.get('house_no', '')} {r.get('street_name', '')}".strip()
                    r["work_description"] = r.get("job_description") or r.get("work_type")
            elif metro["city_key"] == "montgomery_md":
                for r in raw_records:
                    r["permit_number"] = r.get("permitno")
                    r["street_address"] = f"{r.get('stno', '')} {r.get('stname', '')} {r.get('suffix', '')}".strip()
                    r["estimated_cost"] = r.get("declaredvaluation")
                    r["work_description"] = r.get("description")
            elif metro["city_key"] == "sonoma_ca":
                for r in raw_records:
                    r["permit_number"] = r.get("file_number")
                    r["street_address"] = r.get("address")
                    r["estimated_cost"] = r.get("value")
                    r["work_description"] = r.get("description")
            elif metro["city_key"] == "framingham_ma":
                for r in raw_records:
                    r["permit_number"] = r.get("permit")
                    r["street_address"] = f"{r.get('street_number', '')} {r.get('street_name', '')}".strip()
                    r["estimated_cost"] = r.get("estimated_job_cost")
                    r["work_description"] = r.get("description")
            
            # Normalize
            batch_res = batch_normalize_permits(
                raw_records=raw_records,
                source="socrata",
                jurisdiction=metro["jurisdiction"],
                state=metro["state"],
            )
            
            # Deduplicate
            unique_permits, dups_removed = deduplicate_permits_in_memory(batch_res.records)
            total_duplicates_removed += dups_removed
            
            # Upsert into active in-memory warehouse
            for permit in unique_permits:
                _PERMIT_WAREHOUSE[permit.id] = permit
                
            total_normalized += len(unique_permits)
            print(f"[{metro['jurisdiction']}] Ingested {len(unique_permits)} permits into warehouse")

        # 2. Harvest Tier 3 Tyler EnerGov / CSS Metros
        for eg_metro in TIER3_ENERGOV_CONFIGS:
            raw_eg_records = await harvest_energov_metro(client, eg_metro)
            if not raw_eg_records:
                continue

            total_raw += len(raw_eg_records)

            # Normalize using EnerGov normalizer
            batch_res = batch_normalize_permits(
                raw_records=raw_eg_records,
                source="energov",
                jurisdiction=eg_metro["jurisdiction"],
                state=eg_metro["state"],
            )

            # Deduplicate
            unique_permits, dups_removed = deduplicate_permits_in_memory(batch_res.records)
            total_duplicates_removed += dups_removed

            # Upsert into active warehouse
            for permit in unique_permits:
                _PERMIT_WAREHOUSE[permit.id] = permit

            total_normalized += len(unique_permits)
            print(f"[{eg_metro['jurisdiction']}] Ingested {len(unique_permits)} Tier 3 EnerGov permits into warehouse")
            
    # Persist all permits to warehouse_cache.json so FastAPI loads them on reload
    import json
    cache_path = "warehouse_cache.json"
    cache_data = [p.model_dump(by_alias=True) for p in _PERMIT_WAREHOUSE.values()]
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)
    print(f"\nPersisted {len(cache_data)} normalized permits to {cache_path}")

    print("\n==================================================")
    print("  BULK INGESTION SUMMARY                          ")
    print("==================================================")
    print(f"Raw Records Fetched:        {total_raw:,}")
    print(f"Unique Permits Ingested:    {total_normalized:,}")
    print(f"Duplicates Removed:         {total_duplicates_removed:,}")
    print(f"Total Warehouse Count Now:  {len(_PERMIT_WAREHOUSE):,}")

if __name__ == "__main__":
    asyncio.run(run_bulk_ingest())
