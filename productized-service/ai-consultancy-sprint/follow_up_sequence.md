# AI Consultancy Sprint — Follow-Up Sequence

**Goal:** Convert a free-plan request or paid Audit into Build & Deploy ($1,497) → Managed ($497/mo).
**Rule:** Max 1 touch / 2 days. Stop on BUY or explicit "no". Every touch carries a Neteller link.

| # | Day | Channel | Trigger | Message | Link |
|---|---|---|---|---|---|
| 1 | 0 | Email | Plan requested | "Your AI plan is in the works — here's the $297 Audit to get it in 72h" | AI_SPRINT_AUDIT |
| 2 | 2 | Email | No reply | "3 ways [Business] leaks pipeline (and the AI fix for each)" | AI_SPRINT_AUDIT |
| 3 | 4 | Call | No reply | "Following up on your AI plan — 10 min to map your buyers?" | AI_SPRINT_AUDIT |
| 4 | 7 | Email | Audit paid, not Build | "Your plan's done. Next step: we deploy it live in 14 days" | AI_SPRINT_BUILD |
| 5 | 10 | Call | Build not paid | "What's blocking the deploy? I can start the lead feed today" | AI_SPRINT_BUILD |
| 6 | 14 | Email | Build paid | "Live. Want us to run it monthly + keep leads fresh?" | AI_SPRINT_MANAGED_MO |
| 7 | 21 | Email | Managed not started | "Your first month of fresh verified leads is ready — turn it on?" | AI_SPRINT_MANAGED_MO |

## After-call automation (if dialer/OmniRoute connected)
- Tag lead: `sprint_audit` / `sprint_build` / `sprint_managed`.
- On payment webhook (Neteller manual confirm) → send kickoff email + Calendly-style booking note.
- On no-pay at Day 7 → move to Build sequence.
- Suppress on "STOP"/DNC.

## Booking path
1. Lead pays Audit (Neteller AI_SPRINT_AUDIT) OR requests free plan (mailto form).
2. Within 24h: kickoff email with 3 questions (business type, lead spend, current sources).
3. 20-min kickoff call booked → deliver plan in 72h.
4. Upsell Build → Managed via the sequence above.

## Fulfillment path
- Audit: human-built plan PDF + 5 scripts + lead-source map (72h).
- Build: deploy AI cold-calling assistant + connect verified lead feed + follow-up automation + analytics (14d).
- Managed: monthly lead refresh + monitoring + reporting ($497/mo).
