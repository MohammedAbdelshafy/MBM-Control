# P4_FIRST_CUSTOMER — Campaign Tracker

**Product:** P4 — AI Lead Qualification Agent (DFY Lead List Cleaner)
**Offer:** $499 one-time cleanup (up to 10,000 leads, 48h turnaround) / free 1,000-lead sample / from $49/mo monthly qualification
**Campaign objective:** First paying customer for the lead-cleaning service.
**Started:** 2026-08-19
**Status:** BUILDING (runner done, demo validated, landing + payment ready, prospects sourced)

---

## Prospect batch 1 — real contacts from workspace meeting briefs (no fabrication)

All rows are real businesses with real phones/emails already in `MBM/Artifacts/meeting_brief_*.md`.
Outreach angle: lead-quality audit — every one of these businesses is a lead buyer or high-intent
pipeline owner whose lists deserve the same verification we run on our own dialer.

| # | Contact | Company | Phone | Email | Intent | Source | Status | Notes |
|---|---------|---------|-------|-------|--------|--------|--------|-------|
| 1 | Marcus Vance (Founder) | Apex Mechanical & Air Solutions | +1 214 884 9120 | marcus@apex.com | 100/100 HOT | meeting_brief_apex | PENDING | HVAC = local home services; buys homeowner leads |
| 2 | Dr. Elena Vasquez (Owner) | Luxe Sculpt & Aesthetics Med Spa | +1 817 992 4401 | drvasquez@luxesculptaesthetics.com | 100/100 HOT | meeting_brief_luxe_sculpt | PENDING | Med spa = high-CAC paid lead buyer |
| 3 | Robert Vance (Managing Partner) | Sterling & Vance Injury Law Firm | +1 214 739 1100 | rvance@sterlingvancelaw.com | 98/100 HOT | meeting_brief_sterling_vance | PENDING | Injury firm = buys case leads; 40% after-hours loss |
| 4 | David Sterling (COO) | Titan Infrastructure & Civil Contracting | +1 713 449 8823 | dsterling@titaninfrastructuretx.com | 95/100 HOT | meeting_brief_titan | PENDING | B2B pipeline owner; bids + subcontractor lists |
| 5 | Greg Thornton (President) | Patriot Commercial Electric & Controls | +1 817 882 9100 | gthornton@patriotelectrictexas.com | 75/100 | meeting_brief_patriot | PENDING | Commercial contractor; property owner lists |
| 6 | HUMAIRA ZAKREA (Owner) | 2 Friends Home Health & Hospice | +1 214 762 6392 | — | 75/100 | meeting_brief_2_friends | PENDING | Referral-network lead lists (MDs, hospitals) |
| 7 | CHRISTOPHER BURDS (Owner) | Ability Pro Therapy, LLC | +1 404 307 9109 | — | 75/100 | meeting_brief_ability_pro | PENDING | Referral-based pipeline |
| 8 | ARCILIO ALVARADO (CEO) | Advantage Medical Group LLC | +1 787 306 8356 | — | 75/100 | meeting_brief_advantage_medical | PENDING | PR territory; referral lists |
| 9 | BECKY WRIGHT (President) | A Step Ahead Pediatric PT, PC | +1 303 750 2995 | — | 75/100 | meeting_brief_a_step_ahead | PENDING | Referral-based pipeline |

**P4 conversion funnel**
1. Send free 1,000-lead sample offer (or full audit pitch if already an active outreach thread).
2. Clean the sample for free → shows them the dead/duplicate/suppressed portion.
3. Convert to $499 full cleanup (up to 10k) → upsell monthly qualification → upsell lead packs + dialer.

**Reuse rule:** these businesses are already AI-assistant prospects (P5/P1). P4 is a front-door
offer: cheap, fast, undeniable before/after. It warms the account for the bigger retainer.

---

## Campaign execution log

| Date | Action | Target | Result |
|------|--------|--------|--------|
| 2026-08-19 | Built DFY runner + demo; verified Neteller checkout | — | Runner produces cleaned.csv + summary.json + report.md |
| 2026-08-19 | Landing page live (SEND YOUR LIST / FREE 1,000-LEAD SAMPLE CTAs) | — | productized-service/p4-lead-cleaner/landing.html |
| 2026-08-19 | Sourced 9 real prospects from meeting briefs | batch 1 | 9 PENDING — ready to contact |

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