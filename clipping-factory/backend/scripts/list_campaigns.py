import asyncio
import json
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("SELECT id, title, status, requirements, platform_name, payout_per_1k_views, clips_generated, clips_submitted, clips_accepted FROM campaigns ORDER BY created_at DESC LIMIT 20"))
        rows = r.mappings().all()
        for row in rows:
            print(json.dumps(dict(row), default=str, indent=2))
            print("---")

asyncio.run(main())
