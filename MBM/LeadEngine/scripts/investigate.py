#!/usr/bin/env python3
"""Investigate duplicates and fix issues."""

import json
from pathlib import Path

# Check duplicates in tonight queue
with open('MBM/LeadEngine/tonight_real_estate_call_queue.json', 'r') as f:
    data = json.load(f)

queue = data['queue']
phones = [l.get('phone') for l in queue if l.get('phone')]
from collections import Counter
phone_counts = Counter(phones)
duplicates = {k: v for k, v in phone_counts.items() if v > 1}
print("DUPLICATE PHONES IN QUEUE:")
for phone, count in duplicates.items():
    leads = [l for l in queue if l.get('phone') == phone]
    for l in leads:
        print(f"  {phone} - {l.get('name')} - {l.get('source')} - {l.get('is_recovered')}")

print("\n" + "="*80)

# Check which existing dialer leads are missing motivation_signals
with open('mbm-dialer/app/public/leads_database.json', 'r') as f:
    dialer = json.load(f)

dialer_re = [l for l in dialer if 'seller' in (l.get('vertical', '') or '').lower()]
print(f"Total dialer RE leads: {len(dialer_re)}")

missing_signals = []
for lead in dialer_re:
    signals = lead.get('details', {}).get('motivation_signals', [])
    if not signals:
        missing_signals.append(lead)

print(f"Dialer RE leads missing motivation_signals: {len(missing_signals)}")
for m in missing_signals[:5]:
    print(f"  {m.get('contact')} ({m.get('phone')}) - {m.get('vertical')}")

# Check the merged dialer preview for duplicates
with open('logs/recovery/dialer_merged_preview.json', 'r') as f:
    merged = json.load(f)

merged_phones = [m.get('phone') for m in merged if m.get('phone')]
phone_counts = Counter(merged_phones)
duplicates = {k: v for k, v in phone_counts.items() if v > 1}
print(f"\nDUPLICATES IN MERGED DIALER ({len(duplicates)}):")
for phone, count in duplicates.items():
    leads = [m for m in merged if m.get('phone') == phone]
    for l in leads:
        print(f"  {phone} - {l.get('contact')} - {l.get('company')} - recovery: {l.get('details', {}).get('recovery_source')}")