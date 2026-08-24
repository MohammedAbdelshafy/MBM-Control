# WHOP_NEXT_10_ACTIONS.md — Jarvis Decision Queue

```yaml
timestamp: 2026-08-24T12:30:00+00:00
owner: ox-alpha
ranking: IMPACT × CONFIDENCE / EFFORT (desc)
execution_rule: one action at a time; verify before advancing.
```

| # | ACTION | WHY | EXPECTED IMPACT | CONF | EFFORT | DEPENDS | VERIFICATION | STATUS |
|---|---|---|---|---|---|---|---|---|
| 1 | **Commit + push the recovered Whop layer & all deliverables** (isolated commits: whop core, server webhook attribution, campaign engine, artifacts) | 4 unpushed commits + entire live-revenue layer is uncommitted; a second crash loses it | protects all revenue infrastructure | 0.99 | S | none | `git log`, CI green on push | READY |
| 2 | **Register Whop webhook + set WHOP_WEBHOOK_SECRET** (exact steps in FIRST_REVENUE_PLAN) | purchases are currently invisible to measurement; blocks PROOF stage | makes revenue measurable | 0.95 | M (manual dashboard) | deploy host reachable | non-smoke row in webhook_log.json after test ping | BLOCKED_ON_HUMAN |
| 3 | **Execute day-1 touches: 25 NPI prospects via DAY1_PLAYBOOK** | funnel has never had input; zero media spend; real phones | first realistic path to $149 | 0.6 | M (human, ~2h) | #2 for measurement only — touches can start now | `funnel()` contacted=25 | READY |
| 4 | **Write the $149 audit fulfillment SOP** (inputs needed from client → 72h checklist → deliverable template) | selling before defining delivery risks refund/broken promise | protects margin + trust | 0.8 | S | none | SOP file reviewed; dry-run audit on own data | READY |
| 5 | **D3/D7 follow-up sequences for non-repliers** (extend playbook, governor-capped) | single touches convert poorly; follow-ups are cheapest conversion lift | +replies without new prospects | 0.55 | S | #3 | contact_log shows follow-up entries; reply count | AFTER #3 |
| 6 | **Add hourly whop sync to schedule.yml** (`npm run whop:report` already exists) | keeps snapshot LIVE_VALID + Telegram digest without manual runs | freshness of truth | 0.9 | S | #1 pushed | cron run logs show fresh last_attempt | READY |
| 7 | **First-purchase playbook trigger**: affiliate enable (`npm run whop:affiliate`) + cross-sell follow-up (recommend_next_product → Voice Factory) | post-purchase is highest-conversion moment for upsell | $297/mo pipeline | 0.5 | S | first purchase | membership event + affiliate link created | AFTER PURCHASE |
| 8 | **Margin instrumentation**: time-track the first audit delivery (start/stop + any API cost) | margin is the least-known dim (scored 20/100); first delivery = first data | turns UNKNOWN margins into evidence | 0.7 | S | #4, first sale | delivery_time + cost recorded against event_id | AFTER SALE |
| 9 | **Promote headline_test_v1** once landing gets UTM traffic from campaign (needs ≥100 views/variant) | experiment built but starved of sample | better CTR on same traffic | 0.5 | S | #3 producing views | experiments.json last_analysis verdict change | AFTER VIEWS |
| 10 | **Second-channel test for Clipping Engine** (post 2 permitted-community posts or content pieces linking to tracked landing) | clipping SKU has zero distribution today; different audience than clinics | opens standalone segment | 0.4 | M | channel rules checked | landing events with new utm_source | QUEUED |

## Explicitly NOT doing now

- No pricing changes (no data to justify; sensitive floor L3).
- No new subsystems (funnel diagnostics, experiments, lifecycle already exist).
- No fabricated testimonials/case studies.
- No scaling outreach beyond 25 until first funnel evidence.
