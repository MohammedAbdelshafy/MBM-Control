# DEPLOY TEST REPORT — 2026-08-14

**Scope:** All four deploy targets (founder-requested): rewards pipeline, frontend,
Clipping Factory Docker stack, Base44 backend.
**Branch:** master (scrubbed) — `1dd5321` at start of session.

---

## 1. Content Rewards Pipeline (MBM-Social) — DEPLOYED + TESTED ✅

Ran the new overnight code against the **real** `CampaignRouter.json` + `RoutingRegistry.json`.

| Check | Result |
|---|---|
| E2E deploy test `e2e_content_rewards.py` | **58/58 PASSED** |
| Discover from real config | 32 campaigns / 5 brands (dontwatchthis, goalmachinez, cutedosage, clippingfactorymbm, twistsrevealed) |
| Plan (no views provider) | honest zeros — `no_views_model` basis, $0 revenue (nothing invented) |
| Plan (reported-analytics provider, simulated Studio CSV) | sorted by net$/min desc; top: clippingfactorymbm "automation" $0.572/min |
| Routing (real registry) | resolves to `yt_clippingfactorymbm` (publish enabled) |
| Submit → submitted → verified state machine | legal/illegal transitions enforced (queued→verified rejected; verified terminal) |
| Estimate ≠ verified (no mixing) | confirmed |
| EWMA RPM learning | prior updated from verified actuals (25/75 blend) |
| Ledger summary + CSV export | correct sums |
| CLI (`discover --rules`, `plan`, `ledger`) | all run against real config; ledger clean (0 rows) |

All state written to temp dirs; repo unpolluted. Note: `python -m mbm_social.content_rewards`
emits a harmless `runpy` RuntimeWarning from the eager package `__init__` import (cosmetic).

## 2. Frontend (Vite/React dashboard) — DEPLOYED + TESTED ✅

| Check | Result |
|---|---|
| `npm run lint` | exit 0 |
| `npm run typecheck` | exit 0 |
| `npm run build` | exit 0 (49.7s, dist/ written) |
| `vite preview` serve (dist) | HTTP 200, root div + title present |

## 3. Clipping Factory Docker Stack — DEPLOYED + TESTED (with findings) ⚠️

- Docker Desktop was off → launched engine (29.6.1). `docker compose up -d` built images
  (~8.8 GB) and brought up **11/11 containers**; postgres/redis/minio reported `healthy`.
- API (`localhost:8000`) serves `/docs` + `/openapi.json` (22 routes incl.
  `/api/v1/campaigns`, `/api/v1/clips`, `/api/v1/pages`, `/api/v1/health/*`).
- Frontend container (`localhost:3000`) serves the Next.js app (HTTP 200, full SSR HTML).
- Auth: HTTP Basic required on data endpoints (401 gate verified).
- **Integration test (workers paused to free CPU):** `GET /api/v1/health/` → **HTTP 200 in 3.0s**
  with full service map: `{"status":"healthy","postgres":"up","redis":"up","minio":"up",
  "celery_workers":{3 online},"queue_depths":{all 0},"failed_tasks_last_hour":0,
  "dlq_size":2626,"system":{cpu:50.9}}`.
- Workers + beat restored to running after test (11/11 up).

### Findings (need action)
1. **Dead-letter queue buildup: 2626 tasks** (`dlq_size: 2626`, alert level warning). Drain +
   inspect why tasks fail. No tasks failed in the last hour (build-up is historical).
2. **Host CPU saturation** while workers run (worker-video ~180%, redis ~250%) starves the API:
   authenticated `/api/v1/campaigns` hangs (curl 000, ignored `--max-time`). Retried with workers
   paused — health returned fast; the campaigns endpoint still timed out once. Needs a follow-up
   on a quieter host or with `--reload` disabled in the api service.
3. **`docker-compose.yml` obsolete `version:` key** warning; compose also uses `--reload` on the
   API service (prod should not).
4. **Default/placeholder secrets in the stack env** (admin `change-me-admin-password`, `APP_SECRET_KEY`,
   `NEXTAUTH_SECRET` placeholders) and a live-looking `CLIPPING_PASSWORD` in `clipping-factory/.env`.
   Rotate/redact before exposing; verify `.env` is gitignored.

## 4. Base44 Backend — BLOCKED (soft) ⚠️

`base44` CLI is on PATH (`C:\Users\omare\AppData\Roaming\npm\base44.ps1`) but was unresponsive
(no output within 60s) under current host load (Docker stack + workers + OneDrive saturated the
machine). Not started this session. Retry on a quieter host.

---

## NEXT_ACTIONS

1. Drain/rebuild the 2626-task dead-letter queue; fix the root failure cause.
2. Disable `--reload` in the api compose service and remove the obsolete `version:` key.
3. Rotate stack secrets (`.env`), confirm gitignore, and use non-placeholder admin credentials.
4. Re-run `/api/v1/campaigns` auth test on a quiet host (workers stopped) to validate postgres path.
5. Re-attempt `base44 dev` on a quiet host (founder decision on which Base44 app/project).