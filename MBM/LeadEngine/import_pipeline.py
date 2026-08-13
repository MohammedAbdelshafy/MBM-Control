import csv
import os
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.resolve()
CSV_FILE = BASE_DIR.parent.parent / "top_200_prospects_to_call_today.csv"
PIPELINE_DIR = BASE_DIR.parent / "Pipeline"
PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_FILE = PIPELINE_DIR / "pipeline.csv"

today = datetime.now().strftime('%Y-%m-%d')
next_fu = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

deals = []
with open(CSV_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        deals.append({
            "company": row["company_name"],
            "email": row["email"],
            "phone": row["phone_number"],
            "solution": row["category"],
            "deal_value": "$10,000",
            "stage": "prospect",
            "last_touch": today,
            "next_followup": next_fu,
            "notes": f"Score: {row['antigravity_score']} | Contact: {row['contact_name']} ({row['title']})"
        })

fieldnames = ['company', 'email', 'phone', 'solution', 'deal_value', 'stage', 'last_touch', 'next_followup', 'notes']

with open(PIPELINE_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(deals)

print(f"[PIPELINE IMPORT] Successfully saved {len(deals)} verified deals to {PIPELINE_FILE}!")
