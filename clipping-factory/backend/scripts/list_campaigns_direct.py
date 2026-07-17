import asyncio
import json
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://clipuser:clippass@localhost:5432/clipping_factory')
    rows = await conn.fetch('SELECT id, title, status, platform_name, payout_per_1k_views, requirements FROM campaigns ORDER BY created_at DESC LIMIT 10')
    for row in rows:
        print(json.dumps(dict(row), default=str, indent=2))
        print("---")
    await conn.close()

asyncio.run(main())
