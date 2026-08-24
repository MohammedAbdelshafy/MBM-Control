# OX ALPHA — LIVE REVENUE HANDOFF (Whop biz_UxlhGUdO9TpGb0)

Date: 2026-08-24 · Author: ox-alpha (opencode session) · Receiver: Antigravity

---

## LIVE ACCOUNT

```
account_id : biz_UxlhGUdO9TpGb0
products   : 5 live, all visibility=visible
plans      : 6 live plans (all usd, buy_now, unlimited stock)
members    : 0  (VERIFIED via fixed /memberships call — no longer UNVERIFIED)
revenue    : UNAVAILABLE (no purchase evidence exists yet)
mode       : PRE_REVENUE
```

## API STATUS

| Endpoint | Call | Status |
|---|---|---|
| products | `GET https://api.whop.com/api/v2/products?company_id=biz_UxlhGUdO9TpGb0` | 200 OK |
| plans | `GET https://api.whop.com/api/v2/plans?company_id=biz_UxlhGUdO9TpGb0` | 200 OK |
| memberships | `GET https://api.whop.com/api/v2/memberships?company_id=biz_UxlhGUdO9TpGb0` | **200 OK (was 400)** |
| sync health | `logs/whop_sync_health.jsonl` | HEALTHY |

## AUTHORIZATION ISSUE — RESOLVED

**Symptom:** `GET /memberships` → HTTP 400 `"You are not authorized - ensure that
you have access to this resource"`.

**Root cause (verified empirically on 2026-08-24 against the live API):**
`whop_monetize.py::cmd_report` scoped the memberships request with the WRONG
parameter name:

```python
whop_rest("/memberships", {"account_id": ACCOUNT_ID, ...})   # 400 unauthorized
whop_rest("/memberships", {"company_id": ACCOUNT_ID, ...})   # 200 OK, total_count=0
```

The endpoint scopes by `company_id`. An `account_id` param produced an
unscoped request that Whop rejects as unauthorized. It was never a key,
permission, or header problem. The same key returns 200 for `/products`
because that call already used `company_id`.

**Fix:** all REST traffic now flows through `MBM/Whop/whop_live.py`, which uses
v2 endpoints + `company_id` scoping exclusively.

## PRODUCT INVENTORY (all prices REAL from live API)

| Product | ID | Price | Billing | Checkout |
|---|---|---|---|---|
| Revenue Audit Engine | prod_L2MmMKYlE9LAv | $149 | one-time | https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ |
| Property Intelligence API | prod_hseWnnhfVigJo | $97/mo | renewal | https://whop.com/checkout/plan_T6t6iMlvJvE9e |
| AI Voice Agent Factory | prod_Y8rcA2dgkbxyZ | $297/mo | renewal | https://whop.com/checkout/plan_ZtH6wc9mYpl3j |
| AI Video Clipping Engine | prod_MaHYZkh3AfEEf | $497/mo & $997/mo | renewal ×2 | plan_KkeWhWGi53doc / plan_HzmxF6LtJcoEG |
| DFY AI Employee Suite | prod_R5uDTAhXCKAcf | $1,997/mo | renewal | https://whop.com/checkout/plan_nqybZK0ZpJS3J |

Full intelligence table (positioning, cross-sell matrix, ladder, recurring
analysis): `python MBM/Whop/whop.py products` or import `whop_product_intel.py`.

## CURRENT DATA STATUS

- Snapshot file `logs/whop_revenue.json`: schema 2, state **LIVE_VALID**,
  carries `last_successful_sync`, `last_attempt`, `failure_reason`, `source`,
  `snapshot_status`.
- Explicit states implemented: `LIVE_VALID / LIVE_PARTIAL / STALE_VALID /
  FAILED / UNAVAILABLE` with carry-forward protection (a failed sync can never
  overwrite the last known-good catalog; verified by test
  `test_ssl_failure_never_destroys_prior_good_snapshot`).
- Honesty semantics enforced: members/revenue report `UNVERIFIED` /
  `UNAVAILABLE` with reasons instead of fake zeros.
- Funnel events land in `logs/revenue_events.jsonl`; per-product attribution
  via `metadata.product_id`.

## FIXES IMPLEMENTED

1. **Memberships authorization bug** — root cause found + fixed; account truth
   now verifiable (`memberships_active = 0` is VERIFIED).
2. **Snapshot protection layer** — new `whop_live.py` with explicit states,
   carry-forward, atomic persistence, and staleness classification.
3. **Product intelligence engine** — new `whop_product_intel.py`: inventory
   table, positioning, product ladder (two entry doors → core → specialized →
   flagship), validated cross-sell matrix `recommend_next_product()`,
   recurring-revenue analysis, first-revenue objective, opportunity queue.
4. **Landing page commerce** — `public/productized-service/
   ai-consultancy-sprint/landing.html#engines` now sells all five live
   products with tracked CTAs (`cta_click` + `checkout_started` +
   `data-product`). Zero dead buttons; legacy sprint CTAs retained and mapped.
5. **Per-product funnels** — `compute_funnel()` now emits `by_product`.
6. **CLI** — `whop.py status` (instant, no network), `sync`, `products`,
   enriched `opportunities`; dashboard PRE_REVENUE banner.
7. **Observability** — every API call logged to `logs/whop_sync_health.jsonl`
   (timestamp/account/endpoint/status/latency/records/error; secrets redacted);
   health computed as HEALTHY/DEGRADED/FAILED/STALE.
8. **QA gate** — `whop_revenue_qa.py` gained regression checks 10–14
   (scoping fix, snapshot protection, CTA audit, cross-sell, PRE-REVENUE).

## TESTS

```
python -m pytest MBM/Whop -q            -> 56 passed (34 existing + 22 new)
python -m compileall MBM/Whop           -> exit 0
python MBM/Whop/whop_revenue_qa.py      -> PRODUCTION READINESS: 100/100
node MBM/Whop/tests/whop_webhook_smoke.mjs -> ALL PASS (real Express boot)
npm run lint && typecheck && build      -> pass
Live sync (2026-08-24)                  -> LIVE_VALID, HEALTHY
```

New critical test: valid snapshot → full SSL failure → prior snapshot preserved.

## BLOCKERS (business, not software)

1. **Zero traffic to tracked CTAs** — plumbing works; nobody has clicked yet.
2. **No Whop webhook registered** on this account → purchases won't hit
   `revenue_events.jsonl` until a webhook subscription points at
   `POST /api/webhook/whop` with `WHOP_WEBHOOK_SECRET` set in env.
3. **Fulfillment cost/margin UNKNOWN** for every product — no evidence exists;
   do not invent.
4. Legacy sprint checkout links point at the OTHER live account
   (`biz_2VDyenKpD0KOyo`) — intentional, both are real and buyable.

## FIRST REVENUE OBJECTIVE

```json
{
  "product": "Revenue Audit Engine",
  "product_id": "prod_L2MmMKYlE9LAv",
  "price_usd": 149,
  "target_audience": "Local service businesses & RE investors already spending on lead gen",
  "CTA": "START $149 AUDIT",
  "landing_path": "public/productized-service/ai-consultancy-sprint/landing.html#engines",
  "success_event": "purchase event with metadata.product_id == prod_L2MmMKYlE9LAv"
}
```

Rationale: lowest friction of the five ($149 one-time), and the repo already
owns outreach assets aimed exactly at this buyer (prospects pool, day-1
scripts, follow-up sequence, GTM scoreboard).

## ANTIGRAVITY EXECUTION QUEUE

1. **Register the Whop webhook NOW** (blocks all purchase measurement):
   dashboard → biz_UxlhGUdO9TpGb0 → webhooks → subscribe
   `payment.succeeded`, `membership.went_valid`, `membership.renewed`,
   `membership.went_invalid` → URL `https://<prod-host>/api/webhook/whop`;
   set `WHOP_WEBHOOK_SECRET` in the host env. Verify with
   `node MBM/Whop/tests/whop_webhook_smoke.mjs`.
2. **Send first 25 outreach messages** using
   `MBM/LeadEngine/day1_direct_outreach.md` sequence with the $149 checkout
   link as primary CTA (UTM-tagged: `?utm_source=outreach&utm_campaign=audit_v1`).
3. **Run daily**: `npm run whop:report` (fresh snapshot) and check
   `python MBM/Whop/whop.py status` → `critical_blockers` must stay `none`.
4. **After first click without purchase**: inspect
   `python MBM/Whop/whop.py funnel` → `by_product.prod_L2MmMKYlE9LAv`;
   fix the leak before buying any traffic.
5. **After first purchase**: run
   `python MBM/Whop/whop_monetize.py affiliate` to enable member referrals,
   then trigger the cross-sell follow-up from `recommend_next_product()` —
   expected next buy: AI Voice Agent Factory.
6. **Schedule hygiene**: keep hourly NPI callsheet cron feeding the Property
   Intelligence API promise (data freshness is the retention story).
7. **Do not** add pricing, testimonials, or margin figures without evidence —
   QA gate and tests will fail you.

---

Output contract: AGENTS.md. Escalation path: whop_governor.py levels for any
outbound customer contact (cooldowns + attempt caps enforced).
