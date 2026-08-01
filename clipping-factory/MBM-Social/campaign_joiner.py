"""Campaign Joiner — Join real clipping campaigns and start earning."""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
from pathlib import Path
from datetime import datetime, timezone

DB_URL = 'postgresql://clipuser:clippass@localhost:5432/clipping_factory'
LOGS_DIR = Path(r'C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadEngine\logs')
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def list_discovered_campaigns():
    """List all discovered campaigns sorted by payout."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, brand_name, payout_per_1k_views, max_payout_cap, 
               status, platform_name, campaign_url, requirements
        FROM campaigns 
        WHERE status = 'discovered' 
        ORDER BY payout_per_1k_views DESC NULLS LAST
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"DISCOVERED CAMPAIGNS ({len(rows)} total) — Ready to Join")
    print(f"{'='*80}")
    
    campaigns = []
    for i, row in enumerate(rows, 1):
        cid, title, brand, rate_1k, budget, status, platform, url, reqs = row
        rate_m = (rate_1k or 0) * 1000
        budget_val = budget or 0
        campaigns.append({
            'id': cid, 'title': title, 'brand': brand,
            'rate_per_1k': rate_1k, 'rate_per_million': rate_m,
            'budget': budget_val, 'platform': platform, 'url': url,
        })
        print(f"  {i:>2}. {title[:45]:<45} | ${rate_m:>6.0f}/M | ${budget_val:>8,.0f} | {platform}")
    
    return campaigns


def join_campaign(campaign_id):
    """Mark a campaign as joined in the database."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE campaigns 
        SET status = 'joined', 
            updated_at = NOW()
        WHERE id = %s
    """, (campaign_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"  Joined campaign: {campaign_id}")


def list_joined_campaigns():
    """List all joined campaigns."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, brand_name, payout_per_1k_views, max_payout_cap, 
               status, platform_name, campaign_url
        FROM campaigns 
        WHERE status = 'joined' 
        ORDER BY payout_per_1k_views DESC NULLS LAST
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"JOINED CAMPAIGNS ({len(rows)} total)")
    print(f"{'='*80}")
    
    for row in rows:
        cid, title, brand, rate_1k, budget, status, platform, url = row
        rate_m = (rate_1k or 0) * 1000
        print(f"  {title[:45]:<45} | ${rate_m:>6.0f}/M | ${budget or 0:>8,.0f} | {platform}")
    
    return rows


def join_top_campaigns():
    """Auto-join the top 5 highest-paying campaigns."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, brand_name, payout_per_1k_views, max_payout_cap, platform_name
        FROM campaigns 
        WHERE status = 'discovered' AND payout_per_1k_views IS NOT NULL
        ORDER BY payout_per_1k_views DESC
        LIMIT 5
    """)
    top = cur.fetchall()
    
    print(f"\nAuto-joining top 5 campaigns:")
    for row in top:
        cid, title, brand, rate_1k, budget, platform = row
        rate_m = (rate_1k or 0) * 1000
        cur.execute("UPDATE campaigns SET status='joined', updated_at=NOW() WHERE id=%s", (cid,))
        print(f"  JOINED: {title} (${rate_m:.0f}/M, {platform})")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nJoined {len(top)} campaigns. Ready for pipeline processing.")


def show_join_instructions():
    """Show manual join instructions for each platform."""
    print(f"\n{'='*80}")
    print("MANUAL JOIN INSTRUCTIONS")
    print(f"{'='*80}")
    
    platforms = {
        'Clipping.net': {
            'url': 'https://clipping.net/auth/login',
            'method': 'Google or Discord OAuth',
            'steps': [
                '1. Go to https://clipping.net/auth/login',
                '2. Click "Continue with Google" or "Continue with Discord"',
                '3. Sign in with abdelshafyclapps@gmail.com',
                '4. Go to Campaigns → Browse active campaigns',
                '5. Click "Join Campaign" on each one',
                '6. Link your TikTok/YouTube/Instagram accounts',
            ]
        },
        'ClipAffiliates': {
            'url': 'https://www.clipaffiliates.com/login',
            'method': 'Google OAuth or username/password',
            'steps': [
                '1. Go to https://www.clipaffiliates.com/login',
                '2. Click "Continue with Google"',
                '3. Sign in with abdelshafyclapps@gmail.com',
                '4. Browse campaigns and click "Join"',
                '5. Connect your social accounts',
            ]
        },
    }
    
    for platform, info in platforms.items():
        print(f"\n--- {platform} ---")
        print(f"  URL: {info['url']}")
        print(f"  Auth: {info['method']}")
        for step in info['steps']:
            print(f"  {step}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'list':
            list_discovered_campaigns()
        elif cmd == 'joined':
            list_joined_campaigns()
        elif cmd == 'join-top':
            join_top_campaigns()
        elif cmd == 'instructions':
            show_join_instructions()
        elif cmd == 'join':
            if len(sys.argv) > 2:
                join_campaign(sys.argv[2])
            else:
                print("Usage: python campaign_joiner.py join <campaign_id>")
        else:
            print("Usage: python campaign_joiner.py [list|joined|join-top|instructions|join <id>]")
    else:
        # Default: show discovered campaigns and instructions
        campaigns = list_discovered_campaigns()
        show_join_instructions()
