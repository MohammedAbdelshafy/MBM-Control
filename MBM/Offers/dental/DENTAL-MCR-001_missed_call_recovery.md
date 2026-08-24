# DENTAL-MCR-001 — Missed Call Recovery

> **STATUS: CANONICAL — LOCKED by JARVIS (2026-08-24).**
> Principles frozen: ONE location · 30 days · callback-only · no primary-line
> answering · human-confirmed booking · clinical/emergency/medication signals
> escalate to humans · full interaction logging · success metric =
> recovered-booking rate vs. practice's own baseline · NO fixed ROI promise.
> Enforcement code: `MBM/LeadEngine/pain_to_offer/` (contract v1.0.0).
>
> Status: `OFFER_READY (template)` · Vertical: U.S. dental practices · Rail: Neteller
> This is a canonical offer template. It binds to a specific practice ONLY after
> per-company evidence exists. Do not send without a filled `company_id` + evidence pack.

---

## Machine-Readable Contract

```json
{
  "offer_id": "DENTAL-MCR-001",
  "company_id": null,
  "company_id_rule": "REQUIRED before outreach. Must reference a verified NPI-registry practice record with evidence pack.",
  "offer_name": "Missed Call Recovery for Dental Practices",
  "pain_category": "missed_inbound_calls_front_desk_surge",
  "one_sentence_pitch": "When your front desk can't pick up, we call your missed patient calls back within minutes and get them reconnected or booked - and you get a weekly log of every call recovered.",
  "problem_statement": "Dental front desks surge in the morning and at lunch. When staff are chairside or mid-call, inbound patient calls hit voicemail, and voicemail converts poorly. New-patient callers rarely try twice.",
  "pilot": {
    "scope": "ONE location. Callback-only: the AI works exclusively on calls that rang unanswered. It does not answer the main line, does not replace staff, does not touch scheduling systems until booking is proven safe.",
    "duration_days": 30,
    "workflow": [
      "1. Practice forwards missed-call notifications (existing phone system feature).",
      "2. AI places a callback within 5 minutes during business hours via voice, then SMS if unanswered.",
      "3. AI identifies intent: new patient / existing patient / reschedule / question.",
      "4. Booking: AI offers the practice's own public booking link or warm-transfers to staff. Staff confirm every appointment.",
      "5. Clinical, emergency, or medication questions: AI says a staff member will call back and flags immediately. No advice given.",
      "6. Every interaction transcribed and logged to a weekly recovery report."
    ],
    "human_oversight": [
      "Staff approve scripts and review transcripts weekly.",
      "All appointments confirmed by a human before finalizing.",
      "Emergency/clinical signals escalated to humans in real time.",
      "Any caller request for a human is honored instantly."
    ]
  },
  "success_metric": {
    "metric": "Recovered-booking rate: eligible missed calls converted to booked or reconnected new-patient visits within 72 hours, divided by total eligible missed calls.",
    "baseline": "Practice's own pre-pilot callback/book rate measured from their call logs in Week 0 (or Week 1 if logs unavailable).",
    "target_policy": "Target set at kickoff FROM the practice's baseline. No fixed ROI number is promised in copy because none has been verified yet."
  },
  "proof_required": [
    "Verified NPI-registry business record (name, practice address, business phone) with source URL + retrieval timestamp.",
    "Week-0 baseline: missed-call count and current callback behavior from the practice's own phone system.",
    "Written consent path for callbacks/SMS compliant with TCPA and state recording-consent rules.",
    "Signed pilot agreement naming success metric and data handling."
  ],
  "expansion_path": [
    "After-hours receptionist (separate evidence gate)",
    "Recall/reactivation of overdue hygiene patients (separate evidence gate)",
    "Pre-visit intake summaries for dentists (clinical adjacency - highest compliance bar)"
  ],
  "risk_notes": [
    "Callers may be patients: collect minimum data, define retention limits, execute BAA before any PHI touches the system.",
    "No diagnosis, no triage, no medication guidance, no emergency instructions beyond contacting emergency services / waiting for staff callback.",
    "Recording disclosure required in two-party-consent states.",
    "Honor do-not-callback requests permanently via suppression list.",
    "Do not use unsourced industry statistics (e.g., '30% of calls missed') in copy until independently sourced."
  ]
}
```

---

## 15-Second Read

**"Your front desk misses calls during the morning rush. We call those patients back within minutes, reconnect or book them, and hand you a weekly log of every recovered call. One location, 30 days, one number to judge us on."**

---

## Offer Structure

**Problem**
Inbound patient calls go unanswered during front-desk surges; voicemail loses new-patient callers.

**Evidence** (honest tiering - see integrity ledger below)
- `PROVEN`: Real practices with real business phones exist at scale via CMS NPI Registry (repo pipeline `npi_verified_callsheet.py`; Cycle-2 audit: 100% phone connectivity, 0% synthetic rows).
- `LEADING HYPOTHESIS`: Front-desk phone surge is the dominant pain theme (25-call controlled sample, Cycle-2 report; overflow positioning overcame the "we have staff already" objection 3 times → 2 demos).
- `UNVERIFIED - DO NOT USE IN COPY`: Industry stats like "~30% of dental calls missed." No source attached anywhere in repo.

**Why it matters**
Each missed new-patient call is a lost high-lifetime-value relationship. The magnitude per practice is unknown until the Week-0 baseline - which is exactly what the pilot measures first.

**Proposed AI workflow**
See `pilot.workflow[]` above. Callback-only, human-confirmed booking, instant escalation of anything clinical.

**Human oversight**
Script approval, weekly transcript review, human confirmation of every appointment, real-time escalation of clinical/emergency signals, instant handoff on request.

**Pilot scope**
One location. Missed-call callbacks only. No primary-line answering. No write access to scheduling systems during pilot.

**Pilot duration**
30 days.

**Success metric**
Recovered-booking rate vs. the practice's own baseline. One metric. Target fixed at kickoff from their data, never from ours.

**Expected outcome**
Recovered bookings + full visibility into when and how many calls they actually miss. Any revenue estimate is computed AFTER the pilot, from pilot data only.

**Expansion opportunity**
Recall/reactivation → after-hours coverage → clinical intake summary (each gated on separate evidence; see `expansion_path`). DentRx is out of scope for this offer entirely.

---

## Evidence Integrity Ledger

| Claim | Status | Source | Timestamp | Gap |
|---|---|---|---|---|
| Dental practices reachable w/ real phones | PROVEN | CMS NPI Registry via `MBM/LeadEngine/npi_verified_callsheet.py` | 2026-08-15 cycle audit | - |
| Front-desk surge = top pain | LEADING HYPOTHESIS | `CYCLE_2_REVENUE_VALIDATION_REPORT.md` §2 (N=25 calls, SalesforceOS events) | 2026-08-15 | Needs per-practice confirmation |
| Overflow framing converts | LEADING HYPOTHESIS | Same report §3 (3 objections overcome → 2 demos) | 2026-08-15 | N too small for copy claims |
| "$1,850 closed won" in Cycle 2 | UNVERIFIED | Report only; no contract artifact located | - | Verify before citing |
| "30% of calls missed" industry stat | UNVERIFIED | None in repo (`VoiceAgencyStudio/business_niches.json` carries it sourceless) | - | Ban from copy |

**Binding rule:** this offer may not be personalized for a specific practice until OX ALPHA 2 delivers a per-company evidence pack meeting `proof_required`.
