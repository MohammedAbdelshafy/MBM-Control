# Phase 2 — Runtime Decision (Step 1)

**Date:** 2026-09-02  
**Status:** Python confirmed as production runtime for `MBM/LeadEngine/spec_ad/`

## Inspection

- **Existing LeadEngine Python conventions:** `MBM/LeadEngine/intelligence/` uses `dataclasses`, frozen configs (`config.py:12` `IntelligenceFlags`), explicit `load_flags()` from env, `types.py:21` `Provenance`/`OpportunityStatus`, `opportunity_queue.py:29` fail-closed transitions, `security.py:32` sanitization. `dialer_verification_gate.py`, `dialer_queue_engine.py`, `property_intel/*` all Python. `pyproject.toml` / `pytest` hermetic.
- **package.json:** Root `type: module` (ESM) but `MBM/LeadEngine/package.json` is TS/Node for `api/` + `workers/` (Fastify/BullMQ). Spec-Ad is orchestration/business, not an API route — Python avoids a bridge.
- **Python/Node boundaries:** `server/` (Node) consumes LeadEngine via Supabase/queue, not direct imports. Introducing a Node/Python bridge for scoring would duplicate business logic and violate "do not silently change behavior".
- **Test conventions:** `MBM/LeadEngine/intelligence/tests/` hermetic `pytest` (pipeline isolation). Node `package.json:9` `npm test` is minimal (`test_email_engine.js`). Spec-Ad tests fit naturally under `pytest`.
- **Deployment:** `MBM/LeadEngine/intelligence` already additive, feature-flagged OFF by default (`INTELLIGENCE_ENABLED`). `spec_ad` follows same.

## Decision

- **Production code lives under `MBM/LeadEngine/spec_ad/` (Python).** Staging JS at `spec-ad-engine/src/` is preserved untouched for reference per instruction ("Do NOT simply delete the old implementation. First inspect it completely.").
- **Ports are faithful:** `dedup.js` → `targeting/dedup.py`, `scoring.js` → `targeting/scoring.py`, `specAdConfig.js` → `config/spec_ad_config.py`. Behavior preserved; weights `HIGH_VALUE_WEIGHTS` sum 100 unchanged, `NEGATIVE_SIGNALS` identical, qualification requires all 5 required signals + no hard negative + `min_icp_score` threshold. No casual weight changes.
- **No bridge:** If a Node service needs targeting, it must call Python via a thin adapter (e.g., Supabase view or explicit subprocess), not duplicate logic. Clean boundary: Node → Supabase `spec_ad_target_accounts` (00020) → Python `TargetAccountRepository`.

## Consequences

- `MBM/LeadEngine/spec_ad/config/spec_ad_config.py:1` (frozen dataclass, env-aware, raises on invalid) mirrors `intelligence/config.py`.
- `MBM/LeadEngine/spec_ad/targeting/*` imports `MBM.LeadEngine.intelligence.security.sanitize_external_text` (not modified).
- JS scaffold remains at `spec-ad-engine/` (untracked) for audit trail; production imports must use `MBM.LeadEngine.spec_ad`.
