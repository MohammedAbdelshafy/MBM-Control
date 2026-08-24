# Pain-to-Offer — SHARED CONTRACT (v1.0.0)

> **Single source of truth.** OX ALPHA 2, OX ALPHA 3, and Antigravity MUST
> import schemas/gates from `pain_to_offer/`. Terminals may not invent
> competing schemas. Owner: OX ALPHA 1. Status: LOCKED for DENTAL-MCR-001.

---

## 0. Frozen Offer Principles (DENTAL-MCR-001)

Canonical template: `MBM/Offers/dental/DENTAL-MCR-001_missed_call_recovery.md`

- ONE location, 30 days, callback-only, no primary-line answering.
- Human-confirmed booking; clinical/emergency/medication signals escalate to humans.
- Full interaction logging.
- Success metric: recovered-booking rate vs. the practice's own baseline.
- NO fixed ROI promise. NO personalization without an OX2 evidence pack.

---

## 1. Data Separation Law

| Targeting evidence proves | It does NOT prove |
|---|---|
| Practice exists (NPI) | The practice misses calls |
| Business phone is real/verified | Call volume or overflow |
| Multiple dentists / locations | Front desk is overwhelmed |

PRIORITY ≠ PROOF. Size never raises a pain score (`scoring.py` enforces this).
A practice may only be described with "Your practice misses calls…" language
when pain status is **PROVEN**. Otherwise the mandated hedge is exactly:
**"Potential missed-call recovery opportunity"**.

Evidence ledger statuses (only these four): `PROVEN`, `LEADING_HYPOTHESIS`,
`UNVERIFIED`, `REJECTED`. UNVERIFIED/REJECTED never enter outbound copy
(`gates.copy_safety`).

---

## 2. OX ALPHA 2 CONTRACT — Evidence Pack Producer

**Deliverable:** per-company `CompanyEvidencePack` (see `schema.py`), serialized via
`pack.to_ox2_contract()`. Required keys are emitted verbatim by that method:
`company_id`, `practice_name`, `practice_type`, `address`, `city`, `state`,
`website`, `NPI_identifier`, `NPI_source`, `NPI_retrieval_timestamp`,
`business_phone`, `phone_source`, `phone_retrieval_timestamp`,
`owner_or_decision_maker`, `decision_maker_role`, `decision_maker_source`,
`practice_location_count`, `evidence_pack` (targeting claims),
`pain_hypothesis`, `pain_evidence`, `pain_confidence`, `evidence_sources`.

Rules:
1. Identity facts come from authoritative registries (CMS NPI Registry is the
   proven base). Every fact carries source + URL + retrieval timestamp.
2. Pain evidence must be independently sourced per company (their own website,
   published job posts, recorded call events, their own public statements).
   Repo-level hypotheses (Cycle-2 sample) may label at most
   `LEADING_HYPOTHESIS` and only as a starting hypothesis to confirm.
3. If evidence is absent: leave fields empty and set
   `pain_hypothesis=UNVERIFIED`. Empty means unknown; unknown stays unknown.
4. Contacts carry `contact_class`: `BUSINESS_PRACTICE` or
   `PROFESSIONAL_PUBLIC` only. `PERSONAL_PRIVATE` is structurally barred from
   all outreach gates. Never record personal emails/phones at all.
5. Deduplicate before submission using `validation.practice_dedupe_key`.
6. GOLD BATCH #1 spec: **10–25 U.S. dental practices**, prioritized
   (in order): owner-led → established → multi-dentist → multi-location →
   plausible front-desk complexity → legitimate public business contact info.
   Prioritization is targeting metadata only; it adds zero score.

**Binding gate** (`gates.offer_binding_gate`) — a pack binds to DENTAL-MCR-001
only when ALL hold:
```
company_id present
+ identity verified (NPI id + source + timestamp)
+ business phone verified (valid NANP + VERIFIED status + source + timestamp)
+ evidence pack non-empty
+ pain_hypothesis ∈ {PROVEN, LEADING_HYPOTHESIS} with ≥1 supported claim
```

## 3. OX ALPHA 3 CONTRACT — Qualification & Queues

Pipeline: EVIDENCE → PAIN SCORE → OFFER SELECTION → CONTACT VERIFICATION →
EMAIL_READY → CALL_READY → CALL QUEUE.

1. Score ONLY packs passing `gates.pain_gate` via `scoring.pain_score`;
   rank via `rank_packs` (score desc, company_id asc — deterministic).
2. OFFER SELECTION: use `offer_binding_gate(pack, offer_id)` per canonical
   offer. DENTAL-MCR-001 competes with future approved offers; select by
   evidence, not default.
3. Contacts enter gates only with verified provenance. Gates:
   - `email_gate`: suppression pass + non-personal class + valid email +
     source + VERIFIED + timestamp + campaign_eligible + supported pain.
   - `call_gate`: valid US number + VERIFIED + source + timestamp +
     company association + confidence ≥ 0.8 + suppression pass.
4. State transitions MUST pass `state_machine.validate_transition`.
5. Emit queues containing ONLY records whose current gate result passed.
6. Antigravity handoff: **only `EMAIL_READY=true` records**, each carrying its
   evidence pack reference and approved copy lines from
   `safe_outreach_claims`.

## 4. ANTIGRAVITY CONTRACT — Email Execution

Receives ONLY email_ready records. Must NOT:
- personalize beyond supplied evidence,
- strengthen hedged phrasing into factual claims,
- contact suppressed/personal contacts,
- invent owners, phones, volumes, ROI.

## 5. Stop Conditions

- No mass prospect collection until OX2 GOLD BATCH passes review.
- No live dialing/emailing from contract changes alone.
- Any gate failure blocks the record; reasons are mandatory output.
