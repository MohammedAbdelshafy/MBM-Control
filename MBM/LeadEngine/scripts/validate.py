#!/usr/bin/env python3
"""Validate generated artifacts."""

import json
import re

# Validate tonight queue
with open('MBM/LeadEngine/tonight_real_estate_call_queue.json', 'r') as f:
    data = json.load(f)

queue = data['queue']
print(f'Total leads: {len(queue)}')
print(f'Recovered: {data["recovered_count"]}')
print(f'Existing RE: {data["existing_re_count"]}')

# Check for duplicate phones
phones = [l.get('phone') for l in queue if l.get('phone')]
unique_phones = set(phones)
print(f'Phones: {len(phones)}, Unique: {len(unique_phones)}, Duplicates: {len(phones) - len(unique_phones)}')

# Check E.164 format
e164_ok = all(re.match(r'^\+1\d{10}$', p) for p in phones)
print(f'All E.164 format: {e164_ok}')

# Check required fields
required = ['name', 'company', 'phone', 'lead_score', 'skip_trace_status', 'motivation_signals', 'why_call_now', 'recommended_opening', 'provenance']
missing_fields = []
for lead in queue:
    for field in required:
        if not lead.get(field):
            missing_fields.append(f'{lead.get("phone")}: missing {field}')

print(f'Missing required fields: {len(missing_fields)}')
if missing_fields:
    for m in missing_fields[:5]:
        print(f'  {m}')

# Check skip-trace states
skip_states = set(l.get('skip_trace_status') for l in queue)
print(f'Skip trace states: {skip_states}')

# Check sources
sources = set(l.get('provenance') for l in queue)
print(f'Sources: {sources}')

# Check recovered vs existing
recovered = [l for l in queue if l.get('is_recovered')]
existing = [l for l in queue if not l.get('is_recovered')]
print(f'Recovered: {len(recovered)}, Existing: {len(existing)}')

# Validate merge preview
print("\n=== MERGE PREVIEW ===")
with open('logs/recovery/dialer_merge_preview.json', 'r') as f:
    merge = json.load(f)
print(f"Existing dialer: {merge['existing_dialer_count']}")
print(f"New recovered: {merge['new_recovered_count']}")
print(f"Alternate phones: {merge['alternate_phones_count']}")
print(f"Total after merge: {merge['total_after_merge']}")

# Validate recovered candidates
print("\n=== RECOVERED CANDIDATES ===")
with open('logs/recovery/recovered_candidates.json', 'r') as f:
    candidates = json.load(f)
print(f"Total candidates: {len(candidates)}")

# Check for duplicates in candidates
cand_phones = [c.get('phone') for c in candidates if c.get('phone')]
cand_unique = set(cand_phones)
print(f"Candidate phones: {len(cand_phones)}, Unique: {len(cand_unique)}, Duplicates: {len(cand_phones) - len(cand_unique)}")

# Check dialer merged preview
print("\n=== MERGED DIALER PREVIEW ===")
with open('logs/recovery/dialer_merged_preview.json', 'r') as f:
    merged = json.load(f)
print(f"Merged dialer total: {len(merged)}")

# Check for duplicates in merged
merged_phones = [m.get('phone') for m in merged if m.get('phone')]
merged_unique = set(merged_phones)
print(f"Merged phones: {len(merged_phones)}, Unique: {len(merged_unique)}, Duplicates: {len(merged_phones) - len(merged_unique)}")

# Validate entity deduplication
print("\n=== ENTITY DEDUPLICATION ===")
with open('logs/recovery/entity_deduplication.json', 'r') as f:
    entities = json.load(f)
new_entities = [e for e in entities if e['is_new_entity']]
alt_phones = [e for e in entities if e['is_alternate_phone']]
print(f"New entities: {len(new_entities)}")
print(f"Alternate phones: {len(alt_phones)}")

print("\n=== VALIDATION COMPLETE ===")