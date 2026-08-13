import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
CSV_FILE = BASE_DIR.parent.parent / "top_200_prospects_to_call_today.csv"
QUEUE_FILE = BASE_DIR / "cold_calling_queue.json"

queue = []
with open(CSV_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        queue.append({
            "queue_id": row["id"],
            "contact_name": row["contact_name"],
            "title": row["title"],
            "entity": row["company_name"],
            "phone": row["phone_number"],
            "email": row["email"],
            "address": row["address"],
            "city": row["city"],
            "state": row["state"],
            "type": row["category"],
            "priority_score": row["antigravity_score"],
            "tier": row["tier"],
            "call_hook": row["call_opening_hook"],
            "status": "QUEUED_FOR_DIALING"
        })

with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
    json.dump(queue, f, indent=2)

print(f"[QUEUE SYNC] Successfully loaded {len(queue)} verified prospects into {QUEUE_FILE.name}!")
