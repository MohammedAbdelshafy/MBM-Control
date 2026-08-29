# Calling Launch Checklist

**Generated:** 2026-08-29T20:54:08Z
**Active Dialer Leads:** 938
**Pilot Batch:** 20 leads

## Pre-Launch Gates

| Gate | Status | Detail |
|---|---|---|
| Count reconciliation | PASS | RAW=4938 ACTIVE=938 BLOCKED=4000 |
| Idempotency | PASS | 4888 unique, 0 dup |
| Script coverage | PASS | 8 segments, 0 missing |
| Timezone compliance | PASS | 0 non-UTC |
| Dialer payload fields | PASS | Missing: {} |
| CALLING_ENABLED=false | PASS | Default safe; requires explicit human approval to enable |
| No real calls/SMS | PASS | READ-ONLY mode confirmed |
| No seller mutations | PASS | No writes to leads_database.json |

## Launch Sequence

1. Review `calling_pilot_20.csv` — confirm top 20 leads are correct
2. Verify CALLING_ENABLED remains `false` in production config
3. Get explicit human approval before enabling dialing
4. After approval, set CALLING_ENABLED=true and dial Prime 20
5. Record REAL outcomes via telephonyProvider.js webhook
6. Never fabricate outcomes — webhook-first law applies

## Rollback Plan

- Set CALLING_ENABLED=false to stop all dialing immediately
- Blocked leads remain blocked; no recycling of BAD_NUMBER/WRONG_PERSON

## Overall Readiness: GO

