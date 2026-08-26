# Micro-Campaign: "Stop losing leads after the phone rings."

Campaign ID: `SOC-MISSEDCALL-001` · Launched: 2026-08-25 · Status: ARMED (0 posts published)

## Rules
- Every post: HOOK → PROBLEM → PROOF → OFFER → CTA → TRACKABLE LINK.
- Proof = our own verifiable assets (live landing page, working checkout,
  verified-lead pipeline screenshots). NO invented client results. Zero
  testimonials until a real customer exists.
- Conversions are counted ONLY from `revenue_events.jsonl`
  (`cta_click` / `checkout_started` with matching `utm_campaign`) — reported by
  `python MBM/LeadEngine/revenue_scoreboard.py`. No analytics evidence = no claim.

## Trackable links
| Asset | URL |
|---|---|
| Audit checkout | `https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ?utm_source=social&utm_campaign=soc_missedcall_001&utm_content=POST_N` |
| Landing | `https://mbm-dialer-app.vercel.app/productized-service/ai-consultancy-sprint/landing.html?utm_source=social&utm_campaign=soc_missedcall_001&utm_content=POST_N` |

---

## POST 1 — Problem/Agitate (LinkedIn + FB groups)
**HOOK:** "A local business can lose $4k/month and the owner never hears the phone ring-out."
**PROBLEM:** Calls at lunch, after hours, during rush → nobody calls back → caller buys elsewhere. Most owners have no idea which calls died unanswered.
**PROOF:** We map this exact leak in a $149 audit — workflow map of where your inbound dies, built from your real call flow, not guesswork.
**OFFER:** 72-hour AI Automation Audit: workflow map → automation opportunities → ROI estimate → prioritized 3-step plan → demo of your top fix.
**CTA:** Run the audit on your intake line:
`https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ?utm_source=social&utm_campaign=soc_missedcall_001&utm_content=post1`

## POST 2 — Demo/Offer (Short-form video script)
**HOOK:** "This is what happens when your phone rings out now." [show ring → silence]
**PROBLEM:** That silence is a customer booking with your competitor.
**PROOF:** Screen-recorded demo: ring-out triggers an automatic second attempt within 60 seconds + text fallback + qualification + calendar request. (Recording to be captured from the live stack before publishing — do not post without it.)
**OFFER:** Missed-Call Recovery pilot. Start with the $149 audit; fee credited if you implement.
**CTA:** Link in bio → `…landing.html?utm_source=social&utm_campaign=soc_missedcall_001&utm_content=post2`

## POST 3 — Objection killer ("We already have a receptionist")
**HOOK:** "Your receptionist answers 9-to-5. Your customers call at 7pm."
**PROBLEM:** Coverage gaps aren't a staffing failure — they're a system gap.
**PROOF:** The fix is arithmetic, not magic: every ring-out gets an automated second attempt + SMS within a minute. We show you exactly where those calls were dying (audit output).
**OFFER:** $149 Automation Audit (72h) → optional Missed-Call Recovery / AI Receptionist implementation, audit fee credited.
**CTA:** `https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ?utm_source=social&utm_campaign=soc_missedcall_001&utm_content=post3`

---

## Publication checklist (per post)
1. Publish on channel with the exact UTM link above.
2. Log post URL + timestamp in `published_posts.jsonl` here.
3. After 48h: run scoreboard; record `landing_cta_clicks` / `checkout_clicks`.
4. Kill/iterate based on click data only.

**Target:** ≥1 checkout_started event before any further content spend.
