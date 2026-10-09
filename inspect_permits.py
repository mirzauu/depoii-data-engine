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
        res = await conn.execute(text('SELECT * FROM normalized_permits LIMIT 1'))
        print("COLUMNS:", res.keys())
        
        # Also let's get some stats on categorization
        types_res = await conn.execute(text('SELECT permit_type, COUNT(*) FROM normalized_permits GROUP BY permit_type ORDER BY COUNT(*) DESC LIMIT 5'))
        print("TOP TYPES:", types_res.fetchall())
        
        status_res = await conn.execute(text('SELECT status, COUNT(*) FROM normalized_permits GROUP BY status ORDER BY COUNT(*) DESC LIMIT 5'))
        print("TOP STATUSES:", status_res.fetchall())
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
