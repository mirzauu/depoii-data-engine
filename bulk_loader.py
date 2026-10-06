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
]

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
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        for metro in METRO_CONFIGS:
            raw_records = await harvest_metro(client, metro)
            if not raw_records:
                continue
            
            total_raw += len(raw_records)
            
            # Map Cambridge-specific fields if needed
            if metro["city_key"] == "cambridge_ma":
                for r in raw_records:
                    r["contractor_name"] = r.get("firm_name") or r.get("applicant_name")
                    r["estimated_cost"] = r.get("building_cost")
                    r["street_address"] = r.get("full_address")
                    r["work_description"] = r.get("proposed_work_description") or r.get("roof_work_description")
            
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
