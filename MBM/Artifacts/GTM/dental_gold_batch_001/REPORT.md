# DENTAL GOLD BATCH 001 — REPORT

```yaml
batch_id: DENTAL-GOLD-001
status: success
owner: human          # nothing was sent; all outbound requires human authorization
timestamp: 2026-08-24T18:15:00Z
terminals_executed: [PROSPECT_INTELLIGENCE, OFFER_DESIGN, CONTACT_VERIFICATION]
```

## What this is

First small gold batch of U.S. dental practice prospects for the AI-services
mission, produced end-to-end through the three-terminal pipeline:

1. **OX ALPHA 2 (Prospect Intelligence)** — 5 research-approved prospects,
   every field source-backed.
2. **Offer Design** — one problem → one offer → one pilot → one metric per
   prospect (`offers_gold_001.json`).
3. **Contact Verification** — hard gate applied; **4 numbers are CALL_READY**,
   6 others recorded but blocked (`contact_verification_gold_001.json`,
   `call_candidates_ranked_gold_001.json`).

## Files

| File | Contents |
|---|---|
| `prospects_gold_001.json` | Full research records + pain hypotheses (evidence/inference/confidence) + exclusion log |
| `offers_gold_001.json` | 5 narrow pilot offers with oversight models and risk notes |
| `contact_verification_gold_001.json` | 11 phone records normalized to E.164 with statuses/methods/timestamps |
| `call_candidates_ranked_gold_001.json` | Ranked CALL_READY candidates with openers |

## The batch (all DFW — matches existing Twilio-bridge dialer geography)

| Rank | Practice | Locations | Owner (verified) | Main line | Pain thesis | Conf. |
|---|---|---|---|---|---|---|
| 1 | Star Sleep & Wellness / Sleep Dallas | 7 | Dr. Brady Kent Smith DDS (NPPES owner; CMO per press) | +18444094657 | Central intake triage + physician-referral coordination across sites | 0.70 |
| 2 | Fame Dental | 1 (5 dentists) | Dr. Amit Merchant DMD (NPPES Managing Member) | +14692751054 | After-hours/overflow call capture for a 7-day same-day-emergency practice | 0.65 |
| 3 | Benham Orthodontics & Associates PA | 2 | Dr. Adam W. Benham DDS MS (NPPES owner) | +12146188182 | Free-consult follow-up completion across Fri–Sun closure | 0.55 |
| 4 | Lone Star Dental Care | 1 (2 dentists) | Dr. Afshin Vahadi DDS (NPPES President; site bio) | +19723357100 | Bilingual after-hours intake for EN/ES-marketed practice | 0.60 |
| 5 | Arnica Dental Care | 1 (solo) | Dr. Anna Vasilev DMD (NPPES owner) | +14694688269 | Treatment-plan follow-up cadence for elective cosmetic plans | 0.45–0.50 |

## Method (why this batch is trustworthy)

- **Anchor:** CMS NPPES registry (same real-data rail as the repo's NPI
  callsheet). Every prospect exists as an organizational NPI row pulled live
  2026-08-24.
- **Corroboration:** each practice's own official website fetched live;
  identity accepted only on name/address/phone cross-match. Two discrepancies
  found and recorded honestly rather than smoothed over:
  - Lone Star: NPPES address stale (2008-era) vs current site address (phone identical → match held).
  - Arnica: registry phone `267-844-5555` absent from live site → status STALE, never exported.
- **Anti-fabrication compliance:** legacy repo dental targets
  (`Premier Smile Partners`, `Summit Dental Group`) are known-fabricated
  (RECOVERY_STATE.md) and were not reused or referenced. No email was guessed;
  only emails published by the practices themselves were recorded. No ROI
  figures invented anywhere.

## Gate status

- Dedupe: PASS (domain/name/address/phone all unique; Smith entity rows merged into one company record).
- Suppression: PASS against current dialer opt-outs at build time — **must be re-run at export time**.
- Campaign eligibility: BLOCKED pending `whop_governor` authorization (outbound = sensitive class, L3 floor ⇒ human sign-off required).

## Errors encountered (non-blocking)

- DuckDuckGo/Mojeek/aggregator fetches blocked (403/transport) → solved via Brave SERP.
- Bing via fetcher unusable (tokenization junk).
- OSM Overpass: no POI coverage for these practices; abandoned.
- Several dead/parked domains probed and discarded (`famedental.com` parked, etc.).

## next_action

1. Human review of ranked candidates + offers (this folder).
2. Authorize outreach level in whop_governor for chosen targets.
3. On approval: re-run suppression check, then hand ONLY CALL_READY records +
   matched offers to OX ALPHA 3. Nothing else crosses the gate.
