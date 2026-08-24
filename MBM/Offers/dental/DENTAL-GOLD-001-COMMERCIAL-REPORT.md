# DENTAL-GOLD-001/002 — OX ALPHA 3 COMMERCIAL REPORT

**Generated:** 2026-08-24 (Terminal 3) · **Input:** DENTAL-GOLD-002.json v2.0 (OX2, incl. GOLD-001 enrichments) + EMAIL-CANDIDATES
**Gate ownership:** OX2 = research only. OX3 = scoring · offers · verification · CALL_READY · EMAIL_READY · queues.

---

## 1. HEADLINE COUNTS

| Metric | Value |
|---|---|
| TOTAL_GOLD | 13 |
| SCORED | 13 |
| CALL_READY | 12 |
| CALL_BLOCKED | 1 (DAZZLE — no operational evidence) |
| EMAIL_VERIFIED (incl. secondary) | 7 |
| EMAIL_READY | 6 |
| EMAIL_BLOCKED | 1 (Alexander — domain has no MX) |
| SUPPRESSED | 0 |
| REJECTED | 0 new (OX2's 11 rejections honored) |

## 2. INDEPENDENT VERIFICATION PERFORMED BY OX3 (this session)

- DNS MX checks on all 7 candidate email domains → 6 PASS, asdentistrytx.com FAIL (no mail exchanger).
- Fresh re-fetches of lonestardentalcare.com, crosstimbersdental.com/contact-us, arnicadentalclinic.com, fame-dental.com, piedental.com, calexanderdds.com with timestamped confirmations.
- Cross Timbers upgrade: contact page publishes `FrontDesk@CrossTimbersDental.com` (better recipient than generic info@) — captured fresh.
- Arnica: single dual-role line (`469 468 8269`) and weekday-only hours re-confirmed verbatim; `drvasilev@` attributed via CMS NPPES DIRECT endpoint (government source) → VERIFIED MEDIUM, kept secondary.
- Benham site refused automated fetch twice → email stands on practice-controlled Instagram bio + own-domain snippet + MX pass (MEDIUM-HIGH).
- Alexander: no on-site email, no on-site corroboration of co-brand domain, no MX → BLOCKED.

## 3. SCORING RUBRIC & INTEGRITY

ev20 / econ20 / freq15 / labor15 / auto10 / dm10 / exp10.
Every record separates **PROVEN** facts from **LEADING_HYPOTHESIS** (labeled, confidence ≤0.70). No hypothesis was converted to fact. No score awarded for size alone.

## 4. TOP 10 CALL QUEUE (full cards in dental_call_queue.json)

| # | Practice | DM | Phone | Score | Offer |
|---|---|---|---|---|---|
| 1 | Star Sleep & Wellness (7 sites) | Dr. Brady Smith | +1 844 409 4657 | 74 A2* | MCR-001 |
| 2 | Cross Timbers Dental | Dr. Brad Revering | +1 972 355 8500 | 73 B1 | AI-RECEPTIONIST |
| 3 | Associates in PIE (3 sites) | Dr. Michael Goodwin | +1 972 538 3700 | 68 B1 | FOLLOWUP-001 |
| 4 | Fame Dental | Dr. Amit Merchant | +1 469 275 1054 | 66 B1 | MCR-001 |
| 5 | Canyon Creek Family Dentistry | Dr. Afshin Azmoodeh | +1 972 644 3800 | 60 N | MCR-001 |
| 6 | Lone Star Dental Care | Dr. Afshin Vahadi | +1 972 335 7100 | 60 N | MCR-001 |
| 7 | Benham Orthodontics (2 offices) | Dr. Adam Benham | +1 214 618 8182 | 57 N | FOLLOWUP-001 |
| 8 | Alexander Cosmetic/Family/Implant | Dr. Christabelle Alexander | +1 972 939 2888 | 54 N | FOLLOWUP-001 |
| 9 | Bear Pediatric Dentistry & Ortho | Dr. Dennis Bear | +1 469 598 2327 | 54 N | MCR-001 |
| 10 | Arnica Dental Care (solo) | Dr. Anna Vasilev | +1 469 468 8269 | 50 N | MCR-001 |

\* A2 by structure (one owner, one line, seven sites) — still zero behavioral pain evidence; Week-0 baseline required at kickoff.
Bench: 11 Advanced Orthodontic Studio (49), 12 Smiles Family Dental (48).

## 5. EMAIL BATCH 1 (6 records — quality over volume)

1. **Cross Timbers** → FrontDesk@CrossTimbersDental.com · AI Receptionist pilot · hook: same-day promise + text line + insurance-by-phone workflow (all verbatim PROVEN)
2. **Associates in PIE** → office@piedental.com · Follow-Up pilot · hook: 3 locations + referring-doctor portal
3. **Fame Dental** → info@fame-dental.com · Missed-Call Recovery pilot · hook: 7-day schedule + same-day emergency exams
4. **Lone Star** → info@lonestardentalcare.com · MCR pilot · hook: bilingual + Tue/Wed-to-7PM + Sat hours + call-to-schedule
5. **Benham Orthodontics** → info@benhamorthodontics.com · Follow-Up pilot · hook: free consults + Fri–Sun closures
6. **Arnica Dental** → contact@arnicadentalclinic.com · MCR pilot · hook: one line, two roles, weekday-only

Copy rules enforced: no missed-call %, no revenue/ROI, no customers/case studies, no HIPAA/FDA claims, no pain asserted as fact ("can land", "may" phrasing only). Objective = 10-minute conversation / pilot discussion. Opt-out line in every body.

## 6. BLOCKED RECORDS (explicit reason codes)

| Record | Code | Detail |
|---|---|---|
| DENTAL-GOLD-002-ALEXANDER (email) | EMAIL_DOMAIN_NO_MX | asdentistrytx.com has no MX; association uncorroborated on own site. CALL_READY unaffected (#8) |
| DENTAL-GOLD-002-DAZZLE (call) | INSUFFICIENT_OPERATIONAL_EVIDENCE | Identity-only record; OX2 pain UNVERIFIED (0.25). Deferred to OX2 deep-dive |
| BEARPED email | CLOUDFLARE_OBFUSCATED | Address exists on contact page but deliberately not decoded by inference — no queue entry |

## 7. FILES DELIVERED

- MBM/Offers/dental/dental_gold_scored.json
- MBM/Offers/dental/dental_gold_offers.json
- MBM/Offers/dental/dental_gold_verified_contacts.json
- MBM/Offers/dental/dental_email_queue.json (+ DENTAL_EMAIL_QUEUE.md)
- MBM/Offers/dental/dental_call_queue.json
- MBM/Offers/dental/dental_batch1.json

Dialer DB untouched this mission (read-only duplicate check only: 0 phone/NPI overlaps).

## 8. NEXT ACTIONS

1. Human review of Batch 1 emails → Antigravity activation (EMAIL_READY=true exists for exactly 6 records).
2. Mohammed dials CALL QUEUE #1–#5 (dental_batch1.json).
3. Log outcomes to a clean store; re-rank after batch per standard loop.
4. OX2 deep-dive: DAZZLE operational evidence; Breckinridge/Hutcheson pending-tier retries; BearPed email de-obfuscation via manual browser read.
