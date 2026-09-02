# License & Commercial Review — Intelligence Layer
Generated: 2026-09-02
Status: DRAFT — requires human/legal sign-off before prod.

> This file records what was inspected. It does NOT provide legal conclusions.

## Policy

New intelligence layer consumes providers via **documented APIs/MCP**, not by vendoring provider source code. This avoids AGPL copyleft triggering for the host app. Any future decision to vendor or modify AGPL code must be reviewed separately.

## Providers

### 1. World Monitor — `koala73/worldmonitor`
- Canonical repo: `https://github.com/koala73/worldmonitor` (per prompt; verify via GitHub before prod)
- Canonical site: `https://worldmonitor.app`
- License observed: **AGPL-3.0** (from repo LICENSE file — re-verify at verification date)
- Code consumed directly? **No.** Adapter (`world_monitor_adapter.py:18`) uses hosted REST/MCP. No source copied.
- API/MCP surfaces: MCP, REST/OpenAPI, SDKs, CLI (per docs). Adapter discovers tools dynamically; no hardcoded tool list.
- Commercial restrictions: AGPL requires source disclosure **only if** you distribute/modify AGPL code. Consuming the hosted service via API/MCP is **generally** not a distribution of AGPL code, but self-hosting or vendoring would change obligations. Flagged for legal confirmation.
- Attribution: Required only if AGPL code is distributed. API consumption still requires respecting ToS/rate limits.
- Redistribution implications: Do not bundle `worldmonitor` server code into MBM image without legal review. Prefer hosted/MCP.
- Verification date: 2026-09-02 (stub; re-verify repo URL + license file + README before shipping)
- Confidence: **High** that consumption-via-API design avoids AGPL distribution trigger; **Needs verification** of repo + live endpoints.

### 2. Topview — topview.ai
- Repo: vendor GitHub presence (API repo) — URL not yet verified. `provider_policy:topview` is `allow_pending_verification`.
- License: Unknown (proprietary SaaS). Confirm Terms of Service + API ToS before prod.
- Code consumed directly? No — `topview_adapter.py` calls REST if `TOPVIEW_API_KEY` set; otherwise returns `BLOCKED` job (no mock).
- Commercial restrictions: Requires paid API access; quota applies.
- Unresolved: Confirm official API base URL (`api.topview.ai`) + auth scheme + GH org before removing `_pending_verification`.
- Verification date: 2026-09-02 — **NOT_VERIFIED**

### 3. SkySnail — skysnail.ai
- License: Proprietary SaaS.
- Code consumed directly? No — `skysnail_adapter.py` calls REST if key set.
- Verification: **NOT_VERIFIED** — confirm base URL + API docs before prod.

### 4. Anderro — anderro.com
- License: Proprietary marketplace.
- Code consumed directly? No — `anderro_adapter.py` treats rates as live data only.
- Verification: **NOT_VERIFIED** — confirm whether a public JSON API exists; current adapter degrades to `NOT_VERIFIED` placeholders when `ANDERRO_API_KEY` absent (correct per policy: never invent rates).
- Note: Commission claim “50%” is **not** hardcoded; validated live per offer.

### 5. VoxCPM — canonical open-source project
- Repo: Identify canonical VoxCPM org/repo (prompt warns `voxcpm.net` is NOT canonical). `provider_policy:voxcpm_net` is **blocked**.
- License: Open-source (exact license TBD on verification — inspect repo before enabling).
- Code consumed directly? No — `voxcpm_gate.py` is a consent gate only; no TTS runtime vendored. Self-host behind `VOXCPM_ENABLED=true`.
- Commercial restrictions: Project warns about misuse; production/commercial use requires rigorous testing + safety evaluation.
- Status: `gated` + kill switch (`VOXCPM_ENABLED=false` default). Hard bans on impersonation.
- Verification date: 2026-09-02 — **NOT_VERIFIED** (repo URL + license TBD)

### 6. Famelack
- Status: `research_only`. Aggregator linking to public streams; explicitly cannot guarantee copyright status. Never called from production publish path.

### 7. AnkerGames / Vidbox.dev / voxcpm.net
- Status: `blocked`. Never integrated. Code enforces at runtime (`provider_policy.assert_allowed`).

## AGPL Note (World Monitor)

- Current design: **API/MCP consumer only** — host app does not include AGPL files. This is the intended posture per prompt §4/§19.
- If you later self-host `koala73/worldmonitor` or copy its code into the repo, AGPL obligations apply (offer source to users of the modified work, network-use clause). Get legal sign-off first.
- Recommendation: Keep World Monitor as a hosted dependency; pin to a verified tag; add ToS review to runbook.

## Env / Secrets

All provider credentials are env-only (`WORLDMONITOR_API_KEY`, `ANDERRO_API_KEY`, `TOPVIEW_API_KEY`, `SKYSNAIL_API_KEY`). Never logged, never committed (see observability redaction + audit log).

## Outstanding Legal Questions

- [ ] Confirm `koala73/worldmonitor` repo URL + AGPL file + recent commit activity (owner verification)
- [ ] Confirm World Monitor hosted ToS / commercial-use clause
- [ ] Verify Topview API ToS + GH repo ownership
- [ ] Verify SkySnail ToS
- [ ] Verify Anderro API availability + rate limits
- [ ] Identify canonical VoxCPM repo + license + production-use warning scope
