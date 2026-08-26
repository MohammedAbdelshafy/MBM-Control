# Whop Webhook Activation Runbook — biz_UxlhGUdO9TpGb0

Status before runbook: code complete (HMAC-SHA256 verify, idempotent store,
revenue-event normalization in `server/index.js`), secret provisioned locally,
**registration = the only remaining human step.**

## What already exists (verified)

| Piece | Location | State |
|---|---|---|
| Endpoint | `POST /api/webhook/whop` | LIVE in server/index.js:675 |
| Signature check | `x-whop-signature` HMAC-SHA256 over raw body, timing-safe | DONE |
| Idempotency | dedupe by Whop event id → `MBM/Whop/webhook_log.json` | DONE |
| Normalization | Whop action → canonical revenue_event (`purchase`, `subscription_started`, `refund`, `churn`, …) | DONE |
| Store | append-only `MBM/Whop/logs/revenue_events.jsonl` (idempotent by event_id) | DONE |
| Failure observability | `MBM/Whop/logs/webhook_failures.jsonl` | DONE |
| Secret | `WHOP_WEBHOOK_SECRET` in `.env` (generated 2026-08-25, value hidden) | DONE |

## Human steps (dashboard, ~3 minutes)

1. Log in to Whop → company **biz_UxlhGUdO9TpGb0** → Settings → Webhooks.
2. Create webhook:
   - URL: `https://mbm-dialer-app.vercel.app/api/webhook/whop`
   - Events: `payment.succeeded`, `payment.failed`, `membership.went_valid`,
     `membership.went_invalid`, `membership.renewed`, `refund`
   - Signing secret: paste the exact `WHOP_WEBHOOK_SECRET` value from `.env`
     (reveal with: `Select-String -Path .env -Pattern 'WHOP_WEBHOOK_SECRET'`).
3. Click **Send test event** in the dashboard.
4. Verify locally within a minute:
   ```powershell
   Get-Content MBM/Whop/webhook_log.json -Tail 5
   Get-Content MBM/Whop/logs/revenue_events.jsonl -Tail 3
   ```
   A test event must appear in both. If signature rejected → secret mismatch;
   re-copy from `.env`.
5. Delete the test event row from `webhook_log.json` afterwards so dashboards
   stay clean (keep revenue_events audit line; it is marked as test).

## Post-activation scoreboard effect

`python MBM/LeadEngine/revenue_scoreboard.py` will count real
`checkout_clicks` / `payments` / `revenue` automatically — no code changes.

## Rule

No purchase is ever recorded without this webhook firing. There is no manual
"mark as paid" path. Zero simulated purchases, forever.
