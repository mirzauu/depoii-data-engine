import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    load_dotenv('d:/projects/Roofx/depoii-data-engine/.env')
    db_url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(db_url)
    
    async with engine.connect() as conn:
        res = await conn.execute(text('SELECT jurisdiction, COUNT(*) FROM normalized_permits GROUP BY jurisdiction ORDER BY COUNT(*) DESC'))
        rows = res.fetchall()
        print(f"Total Unique Jurisdictions: {len(rows)}")
        for r in rows:
            print(f"{r[0]}: {r[1]}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
