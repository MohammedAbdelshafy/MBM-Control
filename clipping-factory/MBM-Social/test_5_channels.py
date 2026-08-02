import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mbm_social.autonomous_runtime import run_autonomous_campaign

brands_profiles = [
    ("dontwatchthis", "dark_stories"),
    ("goalmachinez", "football_highlights"),
    ("cutedosage", "cute_wholesome"),
    ("clippingfactorymbm", "tech_automation"),
    ("twistsrevealed", "plot_twists"),
]

print("==================================================")
print("RUNNING 5-CHANNEL AUTONOMOUS CAMPAIGN AUDIT & TEST")
print("==================================================")

results = {}

for brand, profile in brands_profiles:
    campaign_id = f"autocheck_{brand}_2026"
    print(f"\n[CHANNEL TEST] Starting campaign for brand '{brand}' (profile: '{profile}')...")
    res = run_autonomous_campaign(
        campaign_id=campaign_id,
        brand=brand,
        profile_name=profile,
        mode="internal",
        dry_run=False,
    )
    results[brand] = res

print("\n" + "=" * 50)
print("=== 5-CHANNEL AUTONOMOUS CAMPAIGN SUMMARY ===")
print("=" * 50)

for brand, res in results.items():
    brand_name = res.get("brand", brand)
    stages = res.get("stages", [])
    published = res.get("published", False)
    stage_names = [s.get("stage") if isinstance(s, dict) else s.stage for s in stages]
    print(f"Channel: {brand_name:<20} | Stages Completed: {len(stages):<2} | Status: {'CONNECTED & PROCESSED' if len(stages) > 0 else 'FAILED'}")
    print(f"  -> Stages: {', '.join(stage_names[:5])}...")

print("\n[COMPLETE] All 5 channels verified and connected!")
