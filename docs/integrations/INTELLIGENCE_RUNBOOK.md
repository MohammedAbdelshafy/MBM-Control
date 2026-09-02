# Intelligence → Content → Monetization — Runbook

## 1) What this is

Additive layer under `MBM/LeadEngine/intelligence/` that enhances the existing MBM / LeadEngine stack without replacing it:

```
World Monitor (MCP/REST) -> IntelligenceEngine -> OpportunityEngine -> ContentOrchestrator -> Topview/SkySnail -> QA -> Human Approval -> existing publishing stack
```

All modules are **feature-flagged OFF by default**. Existing lead pipeline (`daily_lead_ingest.py` + `DialerSingleWriter` + `mbm-dialer/app/public/leads_database.json` rev 91 / 4,953 records) is untouched.

## 2) Enable

```bash
# in your local .env (never commit keys)
INTELLIGENCE_ENABLED=true
WORLDMONITOR_ENABLED=true
WORLDMONITOR_API_KEY=...           # from worldmonitor.app
# optional: WORLDMONITOR_MCP_URL, WORLDMONITOR_BASE_URL
INTELLIGENCE_NICHE_KEYWORDS=real estate,wholesale,clinic,ai services
INTELLIGENCE_AUDIENCE_KEYWORDS=investor,homeowner,clinic owner

# monetization (live rates only)
ANDERRO_ENABLED=true
ANDERRO_API_KEY=...

# production engines (pending verification — confirm API ToS first)
TOPVIEW_ENABLED=true
TOPVIEW_API_KEY=...
SKYSNAIL_ENABLED=true
SKYSNAIL_API_KEY=...

# voice clone stays OFF unless you have self-hosted runtime + consent records
VOXCPM_ENABLED=false
```

Flags are read by `MBM/LeadEngine/intelligence/config.py:load_flags()`. No code change needed.

## 3) CLI

```bash
# see allowlist
python -m MBM.LeadEngine.intelligence policy

# discover World Monitor tools (dynamic, cached 10m)
python -m MBM.LeadEngine.intelligence discover

# dry-run ingest (no writes)
python -m MBM.LeadEngine.intelligence ingest --query "ai clinics Dallas" --limit 10

# persist + dedupe to MBM/Artifacts/intelligence/intelligence_events.json
python -m MBM.LeadEngine.intelligence ingest --query "ai clinics" --apply

# ranked opportunities (intelligence + live Anderro offers, never hardcoded rates)
python -m MBM.LeadEngine.intelligence opportunities --query "real estate wholesale" --top 10
```

## 4) Data & Storage (additive)

| Store | Path | Overlaps lead DB? |
|---|---|---|
| intelligence events | `MBM/Artifacts/intelligence/intelligence_events.json` | No |
| generation jobs | `MBM/Artifacts/intelligence/generation_jobs.json` | No |
| creative variants | `MBM/Artifacts/intelligence/creative_variants.json` | No |
| audit log | `MBM/Artifacts/intelligence/audit.jsonl` | No |

Existing `leads_database.json` + `leads_database_revision.json` + `leads_database_audit.jsonl` + `db_backups/` remain sole-owned by `DialerSingleWriter` (§14). Intelligence jobs never write there directly; to enter the dialer they must go via `opportunity -> queue -> SingleWriter` (future wiring, not in this phase).

## 5) Provider Policy (enforced in code)

`MBM/LeadEngine/intelligence/provider_policy.py` is the single source:

| Provider | Status | Meaning |
|---|---|---|
| worldmonitor | allow | primary intelligence |
| topview | allow_pending_verification | verify API before prod |
| skysnail | allow_pending_verification | verify API before prod |
| anderro | allow_pending_verification | live rates only |
| voxcpm_official | gated (`VOXCPM_ENABLED=true`) | consent + provenance required |
| famelack | research_only | never from production |
| vidbox_dev / ankergames / voxcpm_net | blocked | hard refuse |
| unknown | blocked | default |

Every adapter calls `assert_allowed(provider)` before I/O. Test bypass only with `INTELLIGENCE_ALLOW_BLOCKED_IN_TESTS=true`.

## 6) Security

- Env-only credentials, redacted in `observability.AuditLog`.
- Request timeout (12–15s) + bounded retries (3) with exponential backoff.
- Rate-limit awareness (`429 -> RATE_LIMITED`, retryable).
- Schema validation + payload-size caps (1–2 MB).
- URL allowlist / SSRF guard per adapter.
- Content-type validation + idempotency keys.
- Audit logging per call; no secrets in logs.

## 7) Human Approval Gate

`ContentOrchestrator` never auto-publishes. `create_drafts=true` still produces `GenerationJob` (QUEUED/RUNNING) and `CreativeVariant` (generated) that must pass QA + human approval before `publishing` / existing `clipping-factory` stack.

## 8) Observability

- `MBM/LeadEngine/intelligence/observability.py`: counters (`requests/successes/failures/rate_limited/blocked/auth_failures`), latency p50/p95/avg, audit log.
- `python -c "from MBM.LeadEngine.intelligence.observability import snapshot; print(snapshot())"`

## 9) Testing

```bash
python -m pytest MBM/LeadEngine/intelligence/tests -q   # 25 tests, hermetic
python -m pytest MBM/LeadEngine/tests/test_dialer_integrity_gate.py -q  # existing invariant
```

Invariant: intelligence failure returns `{ok:false, code:...}` and never raises into the lead pipeline.

## 10) Rollback

Feature-flag rollback is instant (no migration):

```bash
# disable everything
INTELLIGENCE_ENABLED=false
# or per-provider
WORLDMONITOR_ENABLED=false
TOPVIEW_ENABLED=false
VOXCPM_ENABLED=false
```

Code rollback: `git revert` the intelligence directory + env additions. Intelligence artifacts are additive files under `MBM/Artifacts/intelligence/` — delete the directory to purge. No migration to undo, no lead DB touch, no queue to drain. Existing tests remain green.

## 11) License Notes

See `docs/integrations/license-review.md`. World Monitor is AGPL-3.0 consumed via API/MCP only (no vendored code). Self-hosting/vendoring triggers AGPL obligations — get legal review first.

## 12) Next Steps (Highest-Value)

1. Verify World Monitor live endpoints (confirm `worldmonitor.app` REST/MCP paths + auth) and replace discovery fallbacks with documented paths.
2. Verify Topview/SkySnail/Anderro official API surfaces and remove `_pending_verification`.
3. Wire `ContentOrchestrator` output into `single_writer_lock` via a flagged adapter (opportunity -> queue -> DialerSingleWriter), with idempotency + dedupe.
4. Add Supabase tables (`intelligence_events`, `content_opportunities`, `affiliate_offers`, `generation_jobs`, `creative_variants`) when persistence outgrows JSON fallback.
