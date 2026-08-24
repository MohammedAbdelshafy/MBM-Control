# GOLD BATCH 001 → OX ALPHA 3 HANDOFF (v2, corrected role)

```yaml
batch_id: DENTAL-GOLD-001
status: success
owner: human
timestamp: 2026-08-24T19:35:00Z
terminal: OX ALPHA 2 — prospect research + evidence collection ONLY
role_correction_acknowledged: true
infrastructure_touched: none
```

## Counters

| Metric | Value |
|---|---|
| TOTAL_RESEARCHED | 24 distinct entities assessed |
| VALID (gold batch) | **10** |
| REJECTED | 11 (incl. 3 parked/wrong-state domains) |
| MISSING_DATA (pending tier) | 5 |
| IDENTITY_VERIFIED | 10 |
| PHONE_FOUND | 10 primary + 7 secondary recorded |
| PAIN_EVIDENCE_FOUND | 9 of 10 carry LEADING_HYPOTHESIS with published-behavior evidence; 1 UNVERIFIED placeholder |

## Canonical handoff file

`MBM/Artifacts/GTM/dental_gold_batch_001/GOLD_BATCH_OX3_HANDOFF.json`

(earlier artifacts in this folder remain valid research history:
prospects_gold_001.json / offers_gold_001.json / contact_verification_gold_001.json /
call_candidates_ranked_gold_001.json / REPORT.md)

## The batch

| # | Practice | City/Locations | NPI anchor | Main line (2-source) | Pain label |
|---|---|---|---|---|---|
| 1 | Star Sleep & Wellness / Sleep Dallas | 7 DFW sites | 1790101020 (+8 rows) | +18444094657 | LEADING_HYPOTHESIS 0.70 |
| 2 | Fame Dental | Frisco (5 doctors) | 1659138956 | +14692751054 | LEADING_HYPOTHESIS 0.65 |
| 3 | Cross Timbers Dental | Flower Mound (3 doctors) | 1285868166 | +19723558500 | LEADING_HYPOTHESIS 0.68 |
| 4 | Benham Orthodontics & Associates PA | Frisco+McKinney | 1437908969 | +12146188182 | LEADING_HYPOTHESIS 0.55 |
| 5 | Bear Pediatric Dentistry & Orthodontics | McKinney | 1285256636 | +14695982327 | LEADING_HYPOTHESIS 0.55 |
| 6 | Lone Star Dental Care | Frisco | 1619123536 | +19723357100 | LEADING_HYPOTHESIS 0.60 |
| 7 | Advanced Orthodontic Studio | Irving+Houston | 1750821666 | +12142727626 | LEADING_HYPOTHESIS 0.45 |
| 8 | Smiles Family Dental | Flower Mound+Arlington | 1881095131 | +19723461100 | LEADING_HYPOTHESIS 0.45 |
| 9 | Arnica Dental Care | Frisco (solo) | 1013674704 | +14694688269 | LEADING_HYPOTHESIS 0.48 |
| 10 | Dazzle Dental Care | Flower Mound | 1043479066 | +19723558568 | UNVERIFIED 0.25 |

## Evidence discipline applied

- IDENTITY EVIDENCE (NPPES rows + live site cross-match) separated from PAIN EVIDENCE throughout.
- Registry facts establish identity only. Every pain item is labeled; no inference is stated as fact.
- PROVEN items are published behaviors (hours, emergency offers, "call to verify insurance", referral desks, review claims). Bottlenecks themselves were never observed and are labeled accordingly.
- No UNVERIFIED claim appears in any outbound-ready copy — OX3 owns all outbound copy generation.
- Discrepancies flagged, never smoothed: Lone Star stale NPPES address; Arnica stale registry number (REJECTED); AOS Carrollton/Irving location ambiguity; Benham co-located second entity; Cross Timbers ↔ 6-Day Dental entity linkage.

## Phone rule compliance

Business/practice numbers only, each with source URL + retrieval timestamp + method.
No guessed digits, no inferred numbers, no personal numbers. CALL_READY is NOT
claimed anywhere in this handoff — that determination belongs to OX3's gate.

## Tooling incidents (documented)

Brave/Bing/DDG/Mojeek/Ecosia rate-limited or blocked intermittently; worked
around via spaced Brave queries + direct domain probing with content-match
verification. Two search-dependent candidates deferred to pending tier rather
than force-resolved.

## next_action

Hand `GOLD_BATCH_OX3_HANDOFF.json` to OX ALPHA 3 for:
SCORING → OFFER SELECTION → CONTACT VERIFICATION GATE → EMAIL_READY → CALL_READY → CALL QUEUE.

STOP CONDITION honored: no mass collection; this is the highest-quality 10-record core with a 5-deep pending bench for batch 002.
