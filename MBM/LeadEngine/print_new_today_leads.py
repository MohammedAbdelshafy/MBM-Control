#!/usr/bin/env python3
import json
from pathlib import Path

db_path = Path("mbm-dialer/app/public/leads_database.json")
leads = json.loads(db_path.read_text(encoding="utf-8"))
new_today_leads = [l for l in leads if l.get("new_today") or l.get("first_seen_at") == "2026-08-16"]

print("=" * 130)
print(f"FIRST 25 REAL NEW TODAY LEADS (Total NEW TODAY: {len(new_today_leads)}):")
print("=" * 130)
print(f"{'#':<3} | {'COMPANY':<35} | {'PERSON':<22} | {'PHONE':<14} | {'SOURCE':<30} | {'VERIFIED':<10} | {'VERTICAL'}")
print("-" * 130)

for idx, l in enumerate(new_today_leads[:25], start=1):
    comp = l.get("company", "")[:35]
    person = l.get("contact", "")[:22]
    phone = l.get("phone", "")[:14]
    source = l.get("source", "")[:30]
    ver_at = l.get("first_seen_at", "")[:10]
    vert = l.get("vertical", "")
    print(f"{idx:<3} | {comp:<35} | {person:<22} | {phone:<14} | {source:<30} | {ver_at:<10} | {vert}")
print("=" * 130)
