# DENTAL-GOLD-002 — OX ALPHA 2 HANDOFF REPORT

```yaml
batch_id: DENTAL-GOLD-002
version: 2.0
terminal: OX ALPHA 2 (research + enrichment ONLY)
timestamp: 2026-08-24T21:40:00Z
boundary: "OX2 does NOT assert CALL_READY or EMAIL_READY. Scoring, offer selection, contact verification, and queues are OX ALPHA 3's exclusive domain. Dialer/production untouched."
```

## Quality report

| Metric | Count |
|---|---|
| TOTAL_RESEARCHED (this cycle) | 18 entities assessed |
| VALID_GOLD_BATCH | **13** |
| IDENTITY_VERIFIED | 13 |
| WEBSITE_VERIFIED | 13 |
| PHONE_FOUND | 13 |
| EMAIL_FOUND | 5 site/page-published FOUND + 3 FOUND_CANDIDATE |
| BOOKING_LINK_FOUND | 8 practices with identified booking/contact route |
| DECISION_MAKER_FOUND | 13 |
| PAIN_EVIDENCE_FOUND | 13 records carry ≥1 operational signal |
| — PROVEN | signals documented per-record (published behaviors) |
| — LEADING_HYPOTHESIS | 12 pain statements |
| — UNVERIFIED | 1 (Dazzle — identity-only depth) |
| — REJECTED | 0 entities this cycle (domain probes logged separately) |
| PENDING | 6 (see below) |

## Batch composition (13 GOLD)

**Enriched from DENTAL-GOLD-001 (10):** Star Sleep & Wellness, Fame Dental, Benham Orthodontics, Lone Star Dental Care, Cross Timbers Dental, Smiles Family Dental, Bear Pediatric, Advanced Orthodontic Studio, Dazzle Dental Care, Arnica Dental Care.
Enrichment added this cycle: booking routes (CareStack portal URL for Cross Timbers; request-page for Bear), public business emails verified to official domains, secondary phones with explicit statuses (CURRENT_OFFICIAL / SITE_PUBLISHED / REGISTRY_ONLY / STALE / REJECTED_FAX), deeper operational evidence (e.g., Canyon Creek-style call-first instructions were already captured; Cross Timbers' payer-logo + "call to verify" workflow; Fame's FlexBook route).

**New prospects (3):**
1. **Associates in PIE** — piedental.com — perio/implant/endo specialty group, 3 locations, all three phones match NPPES digit-for-digit, dedicated referring-doctors referral form, GD-referral testimonial. `DENTAL-GOLD-002-APIE`
2. **Canyon Creek Family Dentistry of Richardson** — canyoncreekfamilydentistry.com — 4 named dentists, JSON-LD phone/address == NPPES, verbatim call-first same-day/emergency instructions. `DENTAL-GOLD-002-CANYONCREEK`
3. **Alexander Cosmetic, Family & Implant Dentistry PLLC** — calexanderdds.com — owner Dr. Christabelle Alexander DDS MAGD, urgent-care Call Now block, insurance-verification-in-first-visit workflow, Mon–Thu hours with always-on intake form; co-brand Alexander & Song at same suite flagged, not merged. `DENTAL-GOLD-002-ALEXANDER`

## Pending tier (6)

| Entity | Blocker |
|---|---|
| Absolute Inwood Dentistry PLLC | No official website discoverable; all domain variants dead |
| Premier Dental Center (Jacob entities, Carrollton+Sachse) | TX web presence unresolved (premierdentalcenter.com = wrong state, rejected) |
| Chansol PLLC | Domain variants dead |
| Breckinridge Dental and Orthodontics | Site up but HTTPS broken (HTTP 526); unreachable this pass |
| Candice Hutcheson DDS MS PLLC (Richardson) | Not yet resolved to official website |
| Alexander/Song entity mapping | Not pending as prospect — flagged relationship inside ALEXANDER record |

## Rejected log (delta)

No new entity rejections this cycle. Dead probe domains logged in the JSON (`rejected_log_delta_batch_002`). Prior batch rejections carry forward in research memory.

## Duplicate/entity control applied

- Smiles Family Dental: two NPI rows + four published numbers reconciled into ONE company entity with location-level phones (both matched respective registry rows).
- Alexander: PLLC + co-brand kept under one company_id with explicit flag; no silent merge.
- Cross Timbers ↔ 6-Day Dental registry row linkage recorded as UNVERIFIED flag, not merged.
- Star Sleep multi-entity rows remain merged (same mainline+fax+owner across all nine).

## ROI statement

Insufficient evidence for reliable ROI estimate on every record. No revenue, missed-call %, or labor figures manufactured anywhere.

## Files

- `DENTAL-GOLD-002.json` — full §18-structure records
- `DENTAL-GOLD-002.md` — this report
- `DENTAL-GOLD-002-EMAIL-CANDIDATES.json` — 8 candidates incl. Arnica special-handling per §16
- `RESEARCH_MEMORY.json` — persistent research history (updated)

## NEXT BATCH

Batch 003 queue: resolve Breckinridge (SSL workaround), Hutcheson, Inwood/Premier-TX/Chansol if new evidence surfaces; then fresh NPPES pulls (Irving, Grapevine, Southlake, Wylie) + first adjacent-vertical scan per mission priority 2.

OX2 RESEARCH COMPLETE — HANDOFF READY FOR OX3
