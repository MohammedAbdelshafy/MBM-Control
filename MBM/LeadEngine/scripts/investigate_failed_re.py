import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from MBM.LeadEngine.dialer_verification_gate import check_lead

data = json.loads(Path("MBM/LeadEngine/real_estate_calling_queue.json").read_text(encoding="utf-8"))
failed = []
for idx, lead in enumerate(data):
    res = check_lead(lead)
    if not res["passed"]:
        failed.append({
            "index": idx,
            "id": lead.get("id"),
            "contact": lead.get("contact"),
            "company": lead.get("company"),
            "phone": lead.get("phone"),
            "reasons": res["rejection_reasons"]
        })

print(f"Total failed: {len(failed)}")
for f in failed:
    print(json.dumps(f, indent=2))
