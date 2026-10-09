import asyncio
import json
from app.extraction.tarrant_parcel_client import TarrantParcelClient

async def main():
    client = TarrantParcelClient()
    print("Testing TarrantParcelClient.fetch_commercial_parcels...")
    parcels = await client.fetch_commercial_parcels(min_sqft=50000, limit=10)
    print(f"\nFetched {len(parcels)} parcels:")
    for idx, p in enumerate(parcels):
        print(f"{idx+1}. [{p['id']}] {p['address']}, {p['city']} | {p['building_sqft']:,} sqft | Owner: {p['owner_name']} | Val: ${p['total_valuation']:,.0f} | ({p['latitude']}, {p['longitude']})")

if __name__ == "__main__":
    asyncio.run(main())
