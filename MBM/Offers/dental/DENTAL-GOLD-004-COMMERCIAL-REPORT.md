# DENTAL-GOLD-004 — OX ALPHA 3 QUEUE DELTA REPORT

**Generated:** 2026-08-25 · **Mode:** delta (no rebuild) · **Dialer:** untouched

## COUNTS
| Metric | Value |
|---|---|
| RESEARCH_INPUT | DENTAL-GOLD-004.json v3.1 (P0 enrichment) |
| TOTAL_GOLD / SCORED | 14 / 14 (13 preserved + Thrive new) |
| OFFER_READY | 13 (12 prior + Thrive AI-PATIENT-INTAKE) |
| CALL_READY | 12 (ranks unchanged) |
| CALL_BLOCKED | 2 — DAZZLE `INSUFFICIENT_OPERATIONAL_EVIDENCE`; THRIVE `PHONE_REGISTRY_ONLY_NOT_WEBSITE_VERIFIED` |
| EMAIL_VERIFIED | 8 total blocks (7 queue primaries + Arnica/drvasilev secondary) |
| EMAIL_READY | **7** (+BearPed info@bearpd.com at rank #6) |
| EMAIL_BLOCKED | 1 — Alexander `EMAIL_DOMAIN_NO_MX` (carried forward) |
| SUPPRESSED | 0 |

## BEAR SPECIAL REVIEW → APPROVED
info@bearpd.com: deterministic Cloudflare-cfemail decode of the practice's own served markup (= published fact, not inference), exact domain match; OX3 independently confirmed Google MX + re-fetched contact page (Dennis Bear DMD / (469) 598-2327 / fax all digit-for-digit). All gate conditions met → EMAIL_READY=true, confidence HIGH. Queue position #6 by composite ranking.

## THRIVE SPECIAL REVIEW
- **WHY IT MATTERS:** strongest research opportunity in batch — multi-site dual-provider group with C-suite, universal same-day promise.
- **PROVEN:** same-day emergency at ALL locations (FAQ verbatim); after-hours explicitly EXCLUDED (verbatim boundary); pre-visit insurance verification institutionalized; $129/mo ortho funnel; single Book Now convergence.
- **LEADING HYPOTHESIS:** staffed-hours intake bottleneck + verification workload (0.65).
- **UNKNOWN:** per-location phones/emails/hours; Garland status; volumes; 6-vs-7 site count (OPEN); Breckinridge succession (OPEN).
- **BEST OFFER:** AI-PATIENT-INTAKE (targets PROVEN verification workflow). **SECOND:** AI-RECEPTIONIST (staffed-hours overflow). **REJECTED for Thrive:** MCR-001 — their published no-after-hours boundary and active same-day culture weaken it.
- **CONTACT STATUS:** identity HIGH, phone REGISTRY_ONLY + number not in handoff → **CALL_BLOCKED** until site-published line captured.
- **PILOT CONCEPT:** one-location intake/verification assistant; **SUCCESS METRIC:** intake-to-verification turnaround vs their own Week-0 baseline (set at kickoff; no promised numbers).
- **BLOCKERS:** contact capture only.

## QUEUE DELTA
- Email queue v2: BearPed inserted #6 (history fields preserved on records 1–5,7).
- Call queue v2: ranks 1–12 unchanged; blocked list now 2 with explicit codes; history stamped.
- batch1: calls top-5 unchanged; emails now 7.
- No record downgraded; no valid contact revoked.

## OX2_NEXT_RESEARCH_ACTIONS (ranked by commercial impact)
1. **Thrive** render-fetch of city/location pages → static NAP matrix incl. main business line (unblocks a 74-score prospect).
2. **Star Sleep** one city-subpage email sweep (adds email lane to call-rank #1).
3. **Fame Dental** verify email on own-domain footer (MEDIUM→HIGH upgrade).
4. **Canyon Creek** booking platform identity + any published email (email lane for top-6 call prospect).
5. **Benham** Lustig entity-role clarity (expansion story).
6. **Alexander** brand-entity mapping is MOOT while asdentistrytx.com lacks MX — needs fresh email discovery instead.

**NEXT_HIGHEST_VALUE_ACTION:** Thrive location-page contact capture (single highest-score unlock available).

## FILES
dental_gold_scored.json · dental_gold_offers.json · dental_gold_verified_contacts.json · dental_email_queue.json · dental_call_queue.json · dental_batch1.json · DENTAL_EMAIL_QUEUE.md — updated under MBM/Offers/dental/.

QC: JSON PASS · dupes 0 · suppression 0 · banned-claim scan 0 · unverified-in-queue 0 · reconciliation: every input record ends SCORED or BLOCKED_WITH_REASON. No silent drops.

**STATUS: READY_FOR_ANTIGRAVITY** (7-record email lane, pending human review). Nothing sent, nothing dialed, production untouched.
