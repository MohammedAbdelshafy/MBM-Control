import asyncio
import json
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://clipuser:clippass@localhost:5432/clipping_factory')
    
    # Get ALL campaigns with full details
    rows = await conn.fetch('''
        SELECT id, title, status, platform_name, payout_per_1k_views, 
               payment_per_accepted_clip, max_payout_cap, requirements,
               clips_generated, clips_submitted, clips_accepted, clips_rejected,
               actual_earnings, source_url, source_type, intelligence_notes,
               due_at, created_at
        FROM campaigns 
        ORDER BY payout_per_1k_views DESC NULLS LAST
    ''')
    
    print(f"Total campaigns: {len(rows)}")
    print("=" * 80)
    
    for row in rows:
        r = dict(row)
        print(f"\nID: {r['id']}")
        print(f"Title: {r['title']}")
        print(f"Platform: {r['platform_name']}")
        print(f"Status: {r['status']}")
        print(f"Payout/1k views: ${r['payout_per_1k_views']}")
        print(f"Payment per accepted clip: ${r['payment_per_accepted_clip']}")
        print(f"Max payout cap: ${r['max_payout_cap']}")
        print(f"Clips generated: {r['clips_generated']}")
        print(f"Clips submitted: {r['clips_submitted']}")
        print(f"Clips accepted: {r['clips_accepted']}")
        print(f"Clips rejected: {r['clips_rejected']}")
        print(f"Actual earnings: ${r['actual_earnings']}")
        print(f"Due at: {r['due_at']}")
        print(f"Created: {r['created_at']}")
        if r['source_url']:
            print(f"Source URL: {r['source_url']}")
        if r['intelligence_notes']:
            print(f"Intelligence: {r['intelligence_notes'][:200]}")
        
        # Parse requirements
        req = r['requirements']
        if isinstance(req, str):
            try:
                req = json.loads(req)
            except:
                pass
        print(f"Requirements:")
        print(json.dumps(req, indent=2))
        print("-" * 80)
    
    await conn.close()

asyncio.run(main())
