import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from textwrap import dedent

async def main():
    load_dotenv('d:/projects/Roofx/depoii-data-engine/.env')
    db_url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(db_url)
    
    queries = {
        "Categories": "SELECT category, COUNT(*) FROM normalized_permits GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10",
        "Statuses": "SELECT status, COUNT(*) FROM normalized_permits GROUP BY status ORDER BY COUNT(*) DESC LIMIT 10",
        "Jurisdictions": "SELECT jurisdiction, COUNT(*) FROM normalized_permits GROUP BY jurisdiction ORDER BY COUNT(*) DESC LIMIT 10",
        "Probable Roof Systems": "SELECT probable_roof_system, COUNT(*) FROM normalized_permits GROUP BY probable_roof_system ORDER BY COUNT(*) DESC LIMIT 10",
        "Storm Window Match": "SELECT is_hail_storm_window, COUNT(*) FROM normalized_permits GROUP BY is_hail_storm_window ORDER BY COUNT(*) DESC"
    }

    async with engine.connect() as conn:
        for title, query in queries.items():
            print(f"\n--- {title} ---")
            res = await conn.execute(text(query))
            for row in res.fetchall():
                val, count = row[0], row[1]
                print(f"{val}: {count}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
