import json
from pathlib import Path

p = Path("mbm-dialer/app/public/leads_database.json")
data = json.loads(p.read_text(encoding="utf-8"))
print(f"Total leads in dialer database: {len(data)}")
print("\n--- TOP 10 CALLABLE LEADS READY FOR DIALING ---")
for i, d in enumerate(data[:10]):
    company = d.get("company", "N/A")
    contact = d.get("contact", "N/A")
    title = d.get("title", "")
    phone = d.get("phone", "N/A")
    vertical = d.get("vertical", "N/A")
    score = d.get("deal_score") or d.get("motivation_score") or d.get("intent_score", 0)
    tier = d.get("tier", "N/A")
    script = (d.get("details", {}).get("Call_Script") or d.get("pitch_angle") or "")[:70]
    print(f"#{i+1:02d} | {score:>3} pts | {tier:<12} | {phone:<14} | {contact:<20} | {company[:30]:<30} | {vertical[:20]}")
    if d.get("details", {}).get("neteller_link"):
        print(f"     Neteller: {d['details']['neteller_link'][:60]}...")
