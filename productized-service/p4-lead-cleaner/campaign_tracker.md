# P4_FIRST_CUSTOMER — Campaign Tracker

**Product:** P4 — AI Lead Qualification Agent (DFY Lead List Cleaner)
**Offer:** $499 one-time cleanup (up to 10,000 leads, 48h turnaround) / free 1,000-lead sample / from $49/mo monthly qualification
**Campaign objective:** First paying customer for the lead-cleaning service.
**Started:** 2026-08-19
**Status:** LAUNCH GATE REVIEWED — PRODUCT READY, PROSPECT EVIDENCE BLOCKED (2026-08-19)

---

## ⛔ Prospect batch 1 — REJECTED (synthetic demo fixtures, not real businesses)

**Blocked reason:** every "prospect" below was sourced from `MBM/Artifacts/meeting_brief_*.md`, but
those briefs are auto-generated from hardcoded demo/sample payloads in the engine code, NOT from
real verified businesses. Evidence:

- Contact names match the legacy synthetic name pools in `MBM/LeadEngine/lead_provenance.py`
  (`SYNTHETIC_FIRST_NAMES` / `SYNTHETIC_LAST_NAMES`): "Marcus Vance", "Robert Vance",
  "David Sterling", "Elena Vasquez", "Greg Thornton", "Christopher Burds" all flagged.
- "Apex Mechanical & Air Solutions" appears as `sample_payloads` in
  `MBM/LeadEngine/gtm_notification_bus.py` and in 8 test files (`test_gtm_*`, `test_telegram_adapter`,
  `test_conversation_engine`, `test_ai_buyer_hunter`, etc.) as a fixture.
- The same records are hardcoded in `ai_assistant_buyer_hunter.py` and `offer_architect.py`.
- `MBM/Artifacts/GTM/meetings/meeting_apex_mechanical___air_solutions.json` has empty
  date/time/pain/why_now — it is a stub, not a booked meeting.
- Email `marcus@apex.com` is a generic placeholder domain with no business-domain evidence.

**Verdict:** these records were produced by the synthetic lead generator that the Real-Lead
Pipeline hygiene gate exists to strip. They must NOT be contacted. Any outreach to them would be
fabricated outreach.

| # | Contact | Company | Phone | Email | Evidence | Status |
|---|---------|---------|-------|-------|----------|--------|
| 1 | Marcus Vance | Apex Mechanical & Air Solutions | +1 214 884 9120 | marcus@apex.com | ❌ synthetic fixture | REJECTED |
| 2 | Dr. Elena Vasquez | Luxe Sculpt & Aesthetics Med Spa | +1 817 992 4401 | drvasquez@luxesculptaesthetics.com | ❌ synthetic name | REJECTED |
| 3 | Robert Vance | Sterling & Vance Injury Law Firm | +1 214 739 1100 | rvance@sterlingvancelaw.com | ❌ synthetic name | REJECTED |
| 4 | David Sterling | Titan Infrastructure & Civil Contracting | +1 713 449 8823 | dsterling@titaninfrastructuretx.com | ❌ synthetic name | REJECTED |
| 5 | Greg Thornton | Patriot Commercial Electric & Controls | +1 817 882 9100 | gthornton@patriotelectrictexas.com | ❌ synthetic name | REJECTED |
| 6 | Humaira Zakrea | 2 Friends Home Health & Hospice | +1 214 762 6392 | — | ❌ demo fixture | REJECTED |
| 7 | Christopher Burds | Ability Pro Therapy, LLC | +1 404 307 9109 | — | ❌ synthetic name | REJECTED |
| 8 | Arcilio Alvarado | Advantage Medical Group LLC | +1 787 306 8356 | — | ❌ demo fixture | REJECTED |
| 9 | Becky Wright | A Step Ahead Pediatric PT, PC | +1 303 750 2995 | — | ❌ demo fixture | REJECTED |

**Next source for a real prospect (in order of trust):**
1. **NPI registry** (`MBM/LeadEngine/npi_verified_callsheet.py`) — every row is a real, licensed
   US healthcare business with a real phone, pulled from the government CMS NPI registry.
2. **Canonical dialer DB** `mbm-dialer/app/public/leads_database.json` — VERIFIED-status rows with
   real provenance (`FRESH_CALL_NOW`, `FRESH_NEXT`, `UNCALLED_VERIFIED` buckets).
3. A genuinely engaged inbound contact (Whop buyer, marketplace inquiry) — real two-way signal.

Do NOT rebuild the outreach until a prospect passes the evidence gate below.

## Prospect evidence gate (P4 LAUNCH GATE Step 1)

| Check | Rule |
|---|---|
| company name | must exist in an authoritative source (registry / county record / verified dialer row) |
| contact name | must be the verified decision-maker on that record |
| email | must be on the business's own domain (no generic @gmail/@apex.com) |
| phone | must pass `dialer_verification_gate.check_lead` |
| source/provenance | must be a real, traceable source (NPI / DCAD / verified dialer row) |
| contact belongs to business | must be attested by the authoritative record |
| not suppressed | phone must NOT be in `MBM/Artifacts/suppressed_bad_phones.json` |
| not duplicated | record must not already be in the canonical dialer as contacted |
| qualification evidence | intent must come from a real signal, not a hardcoded demo payload |

**Any unsupported critical field → OUTREACH BLOCKED.**

---

**P4 conversion funnel**
1. Send free 1,000-lead sample offer (or full audit pitch if already an active outreach thread).
2. Clean the sample for free → shows them the dead/duplicate/suppressed portion.
3. Convert to $499 full cleanup (up to 10k) → upsell monthly qualification → upsell lead packs + dialer.

---

## Campaign execution log

| Date | Action | Target | Result |
|------|--------|--------|--------|
| 2026-08-19 | Built DFY runner + demo; verified Neteller checkout | — | Runner produces cleaned.csv + summary.json + report.md |
| 2026-08-19 | Landing page created (SEND YOUR LIST / FREE 1,000-LEAD SAMPLE CTAs) | — | productized-service/p4-lead-cleaner/landing.html |
| 2026-08-19 | Sourced 9 prospects from meeting briefs | batch 1 | ❌ REJECTED — all synthetic demo fixtures (see above) |
| 2026-08-19 | LAUNCH GATE review | — | PROSPECT EVIDENCE: BLOCKED · OFFER/CHECKOUT/FULFILLMENT/LANDING: PASS |

---

## Delivery pipeline (what the customer receives)

1. Customer sends CSV/JSON (up to 10k) via email (`LEAD CLEAN` subject) or P4 API.
2. `clean_leads.py --input <file>` runs the canonical verification gate + provenance + dedupe + suppression.
3. Deliver: cleaned CSV + summary report + before/after stats + reason codes.
4. No manual edits — every status traceable to a code path (reproducible).

**Proof commands**
```
python productized-service/p4-lead-cleaner/clean_leads.py --demo
python productized-service/p4-lead-cleaner/clean_leads.py --input <customer.csv>
```

---

## P4 FIRST CUSTOMER LAUNCH GATE — 2026-08-19

| Check | Status | Evidence |
|---|---|---|
| prospect: company | ⛔ BLOCKED | All 9 batch-1 "prospects" are synthetic demo fixtures (see above) |
| prospect: contact | ⛔ BLOCKED | Names match `SYNTHETIC_FIRST_NAMES`/`SYNTHETIC_LAST_NAMES` in lead_provenance.py |
| prospect: email | ⛔ BLOCKED | `marcus@apex.com` is a generic placeholder, no business-domain proof |
| prospect: phone | ✅ PASS | Not suppressed, not in quarantine ledger; passes placeholder check |
| prospect: provenance | ⛔ BLOCKED | Briefs generated from hardcoded demo payloads, not authoritative sources |
| prospect: not duplicated | ✅ PASS | Not found as contacted in canonical dialer |
| offer: DFY $499 | ✅ PASS | Landing + dashboard + Neteller `P4_LEAD_CLEAN_DFY_10K` = $499.00, ≤10k, 48h |
| offer: monthly $49/mo | ✅ PASS | Landing + dashboard + `P4_LEAD_CLEAN_MONTHLY_1K` = $49.00 |
| offer: free sample 1,000 | ✅ PASS | Landing + dashboard + `P4_FREE_SAMPLE_1K` = $0.00 |
| offer: no contradiction | ✅ PASS | No conflicting P4 price in server/src/artifacts |
| checkout: CTA → link | ✅ PASS | All CTAs on landing resolve to mailto or in-page anchors; no `#` dead links |
| checkout: product id + amount | ✅ PASS | Decoded all 3 Neteller links → correct wallet (abdelshafyclapps@gmail.com / 4599228811), correct item + amount (499.00/49.00/0.00) |
| checkout: payment confirmed | ⚠️ NOT TESTED | No real charge made; Neteller rail confirmation requires an actual checkout |
| fulfillment: pipeline | ✅ PASS | Input → cleaner → gate → suppression → dedupe → cleaned.csv + summary.json + report.md |
| fulfillment: customer-readable | ✅ PASS | Demo output verified: report.md and cleaned.csv readable, reason-coded, actionable |
| landing: no placeholders | ✅ PASS | No TODO/lorem/example.com/dead `#` links |
| landing: mobile/desktop | ✅ PASS (static) | Responsive grid CSS; real deployment URL not yet verified |
| landing: contact method | ✅ PASS | mailto:abdelshafyclapps@gmail.com with `LEAD CLEAN` / `FREE SAMPLE` subjects |
| landing: deployed URL | ⚠️ NOT VERIFIED | `landing.html` is local-only; not yet hosted |
| outreach: message | ⛔ BLOCKED | Not written — no verified prospect to target |
| outreach: sent | ❌ NOT SENT | No authorized send channel used |

```text
prospect:        BLOCKED (synthetic fixtures)
evidence_verified: no
offer_verified:  yes
checkout_verified: yes (link structure) / payment confirmation pending
outreach_ready:  BLOCKED
outreach_sent:   no
response:        —
next_action:     Source a real prospect from the NPI registry (has real phone +
                 provenance) or a genuinely engaged inbound contact, pass the
                 prospect evidence gate, THEN send the free 1,000-lead sample offer.
```

**Blocker — sourcing real prospects:** the NPI callsheet rows are real (verified via CMS NPI
Registry, source_reference NPI-xxxx, government_registry) but carry no email. Reachable by phone.
The canonical dialer DB is mixed; only rows with provenance + verified phone qualify.