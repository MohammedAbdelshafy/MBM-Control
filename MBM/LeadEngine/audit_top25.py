import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
leads = json.loads((ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json").read_text(encoding="utf-8"))
top25 = [l for l in leads if l.get("main_queue")][:25]

print(f"Top 25 count: {len(top25)}")
print(f"{'Rank':<5} | {'ID':<18} | {'Segment':<20} | {'Vertical':<28} | {'Phone':<15} | {'Fresh':<6} | {'Prio':<5} | {'Script ID'}")
print("-" * 140)
for i, l in enumerate(top25, 1):
    rank = l.get("priority_rank", i)
    lid = l.get("id", "")
    seg = (l.get("segment") or "")[:20]
    vert = (l.get("vertical") or "")[:28]
    phone = l.get("phone", "")
    fresh = l.get("freshness_score", 0)
    prio = l.get("priority_score", 0)
    sid = l.get("script_id", "")
    print(f"{rank:<5} | {lid:<18} | {seg:<20} | {vert:<28} | {phone:<15} | {fresh:<6} | {prio:<5} | {sid}")
