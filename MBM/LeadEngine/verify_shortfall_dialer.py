import json
from pathlib import Path

DIALER_DB = Path("mbm-dialer/app/public/leads_database.json")
data = json.loads(DIALER_DB.read_text(encoding="utf-8"))
leads = data if isinstance(data, list) else data.get("leads", [])

niches = [
    "Commercial Contractors & ConTech",
    "AI Consultancy & Automation",
    "Website Design & Development",
    "Mobile App Development",
    "Professional Services & B2B Agencies",
]

print("=" * 80)
print(f"  TOTAL LEADS IN DIALER DATABASE: {len(leads)}")
print("=" * 80)

for niche in niches:
    niche_leads = [l for l in leads if l.get("vertical") == niche and l.get("callable")]
    print(f"\n--- {niche.upper()} (Total Callable: {len(niche_leads)}) ---")
    for idx, l in enumerate(niche_leads[:3], 1):
        print(
            f"  #{idx:02d} | ID: {l.get('id'):<20} | Co: {l.get('company')[:32]:<32} | "
            f"Contact: {l.get('contact'):<18} | Phone: {l.get('phone'):<14} | "
            f"Bucket: {l.get('queue_bucket'):<14} | Fresh: {l.get('freshness_stage'):<14} | "
            f"Prio: {l.get('priority_score')} | Ver: {l.get('verification_status')}"
        )
print("=" * 80)
