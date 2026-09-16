# P4 Human Review Queue — TOP 10 (all PENDING_REVIEW)

Rules: review each prospect individually. No bulk approve. Approval state
changes only by explicit operator edit of `p4_today_top10.csv`
(`review_status` PENDING_REVIEW → APPROVED / EDITED / DROPPED).
Full bodies: `p4_outreach_queue.json` (25 DRAFT_ONLY, sends: 0).

Global notes (apply to every draft):
- Subject lines are machine-truncated at 60 chars and may cut mid-word —
  rewrite the subject by hand when approving (EDIT, not a defect in claims).
- "Hi there" is used everywhere: no contact names were verifiable. If you
  find a verified name on the prospect's site, personalize on approve.
- Pain lines are labeled hypotheses, proof is the 11-row demo only.

---

## #1 P4-011 — Blueprint Business Solutions
WHY TARGETED: appointment-setting outsourcer; top-of-funnel rows flow into client calendars (rank 0.81).
EVIDENCE: Texas page live Feb-2026; company email + phones published (not delivery-verified).
MESSAGE: subject "Idea for Blueprint Business Solutions: top-of-funnel..." (rewrite: cut off) + 10-minute-look CTA.
RISK FLAGS: none on claims. Contact path: published email/phone (verify on send day).
ACTION: [APPROVE] [EDIT] [DROP]

## #2 P4-013 — EBQ
WHY TARGETED: US appointment setter, 5-touch cadences = repeated dead-record cost (rank 0.81).
EVIDENCE: Austin address/phone/email published, Mar-2026 article (not delivery-verified).
MESSAGE: subject "Idea for EBQ: 5-touch follow-up cadences..." (rewrite: cut off) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

## #3 P4-004 — DFW Off Market Deals (Dallas Homes for Cash)
WHY TARGETED: VIP buyer intake must be matched to deals; intake hygiene is the product (rank 0.785).
EVIDENCE: company line (469) 305-0988 + Dallas office published (not dial-verified).
MESSAGE: subject cut off mid-word (rewrite) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

## #4 P4-010 — HANGAR49
WHY TARGETED: conversation-led outbound; handoff quality is the offer (rank 0.77).
EVIDENCE: company line +1-347-518-4084 published (not dial-verified). No email observed.
MESSAGE: subject cut off mid-word (rewrite) + 10-minute-look CTA.
RISK FLAGS: email channel = website form only (no verified email — do not guess one).
ACTION: [APPROVE] [EDIT] [DROP]

## #5 P4-015 — Visionary Solutions Inc
WHY TARGETED: scaling sales teams multiply list variance (rank 0.77).
EVIDENCE: phone + email published May-2026 (not delivery-verified).
MESSAGE: subject ends "-- my ..." (rewrite fully) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

## #6 P4-018 — NATiVE Solar
WHY TARGETED: door-knock + web leads mix service areas (rank 0.745).
EVIDENCE: email + phone published Jun-2025 (not delivery-verified).
MESSAGE: subject cut off (rewrite) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

## #7 P4-019 — Good Faith Energy
WHY TARGETED: high-volume inbound across DFW cities (rank 0.745).
EVIDENCE: address/phone/email published (not delivery-verified).
MESSAGE: subject cites "770+ review-scale" — THEIR review count, framed as volume. Soften on approve ("high-volume review presence") or drop the number.
RISK FLAGS: third-party stat repeated — human must decide to keep or cut.
ACTION: [APPROVE] [EDIT] [DROP]

## #8 P4-020 — Solar SME
WHY TARGETED: quote-request filtering (renters/out-of-area) (rank 0.705).
EVIDENCE: office/email/phone published (not delivery-verified).
MESSAGE: subject complete + 10-minute-look CTA.
RISK FLAGS: "renters" inference is hypothesis-labeled — keep the label.
ACTION: [APPROVE] [EDIT] [DROP]

## #9 P4-021 — Longhorn Solar
WHY TARGETED: multi-metro household duplication (rank 0.705).
EVIDENCE: Plano office contacts published (not delivery-verified).
MESSAGE: subject ends "--" (rewrite) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

## #10 P4-022 — North Texas Solar
WHY TARGETED: crew utilization depends on appointment quality (rank 0.705).
EVIDENCE: address/email/phone published (not delivery-verified).
MESSAGE: subject cut off (rewrite) + 10-minute-look CTA.
RISK FLAGS: none on claims.
ACTION: [APPROVE] [EDIT] [DROP]

---

## After review
- Approved → send manually (packet: `p4_manual_send_packet.md`), set CONTACTED + timestamp + sender + approval ref.
- Edited → re-check against playbook banned-claim rules before sending.
- Dropped → record reason; never re-add without new evidence.
- Replies → `classify_sales_reply` same day; opt-outs suppressed same day.
