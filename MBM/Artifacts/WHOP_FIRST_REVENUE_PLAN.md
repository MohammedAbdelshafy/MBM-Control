# WHOP_FIRST_REVENUE_PLAN.md — Shortest Path to First Verified Whop Revenue

```yaml
timestamp: 2026-08-24T12:25:00+00:00
owner: ox-alpha
objective: FIRST_VERIFIED_PURCHASE — one real payment.succeeded for prod_L2MmMKYlE9LAv ($149)
campaign: whop_audit_day1 (controlled 25-prospect experiment)
send_policy: HUMAN_APPROVED_ONLY (governor L3) — nothing auto-sends, ever.
```

## The Path (every node's current status)

```
LANDING ─→ CTA ─→ CHECKOUT ─→ PAYMENT ─→ WEBHOOK ─→ FULFILLMENT ─→ PROOF ─→ UPSELL
 ✔LIVE     ✔TRACKED  ✔LIVE LINK  ◻ none yet  ✘UNREGISTERED  ◻SOP MISSING  ◻  ◻
```

| Node | Status | Evidence |
|---|---|---|
| Landing | LIVE | `public/productized-service/ai-consultancy-sprint/landing.html#engines`, served at mbm-dialer-app.vercel.app; QA CTA check PASS |
| CTA tracking | READY (unexercised) | `cta_click` + `checkout_started` beacons with `data-product`; UTM persisted per session |
| Checkout | LIVE | `https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ` — real plan, verified via API today |
| Payment | NONE EVER | memberships VERIFIED = 0; revenue NO_REVENUE_EVIDENCE |
| Webhook | **BLOCKED** | endpoint built+tested (HMAC 401s, dedupe); NOT registered on biz_UxlhGUdO9TpGb0; `WHOP_WEBHOOK_SECRET` not in env |
| Fulfillment | SOP MISSING | audit delivery steps/time never defined — must be written before first sale, not after |
| Proof/upsell | WIRED | cross-sell engine → next buy: Voice Factory |

## MANUAL ACTION REQUIRED (cannot be done programmatically)

Register the webhook in the Whop dashboard for biz_UxlhGUdO9TpGb0:
1. Dashboard → Developer → Webhooks → Add endpoint:
   `https://mbm-dialer-app.vercel.app/api/webhook/whop`
2. Subscribe: `payment.succeeded`, `membership.went_valid`,
   `membership.renewed`, `membership.went_invalid`
3. Copy signing secret → set `WHOP_WEBHOOK_SECRET` in Vercel project env (+ local .env)
4. Redeploy/restart server, then verify:
   `node MBM/Whop/tests/whop_webhook_smoke.mjs` and send Whop's test ping;
   a non-smoke row must appear in `MBM/Whop/webhook_log.json`.

**Do not claim the webhook works until a real signed event lands.**

## Campaign Execution (Phase 12 protocol)

Artifacts already generated (idempotent, dedupe-guarded):
- `MBM/Artifacts/GTM/campaigns/whop_audit_day1/prospects.csv` — 25 rows,
  mission schema (prospect/business/source/channel/message/timestamp/status/
  response/CTA/checkout_started/purchase), all source=CMS_NPI_REGISTRY
- `DAY1_PLAYBOOK.md` — per-prospect 1-click WhatsApp + Gmail links with
  personalized pain-based messages and UTM-tagged landing URLs
  (`utm_campaign=whop_audit_day1&utm_content=AUDIT-XX`)

Operator loop:
```
python MBM/Whop/whop_first_revenue_campaign.py build      # regenerate safely
# work playbook top-down, ONE touch per prospect today
python MBM/Whop/whop_first_revenue_campaign.py mark AUDIT-01 --status contacted
python MBM/Whop/whop_first_revenue_campaign.py funnel     # auto-diagnoses the leak
```

Funnel diagnostics (Phase 13 classifier) is implemented in `funnel()`:
NO_TRAFFIC → TOUCHED_NO_REPLY → REPLY_NO_CHECKOUT → CHECKOUT_NO_PURCHASE →
PURCHASE_NO_WEBHOOK → FUNNEL_HEALTHY. Smoke events are excluded from revenue
counts by design (`smoke_` id guard, tested).

## Hard rules

- No scaling before first funnel evidence.
- No fabricated prospects/replies/purchases (Top-25 list is NPI-real; old
  day1_direct_outreach.py phone list is FABRICATED — do not reuse).
- No margin/testimonial claims until first delivery is measured.
