# Factory recovery matrix (archaeology 2026-09-16)

| Capability | Location | Historical purpose | Current state | Dependencies | Last verified | Security risk | Value | Action |
|---|---|---|---|---|---|---|---|---|
| CanonicalCreator 20k gate | MBM/LeadEngine/canonical_lead_schema.py | Lead-schema creator entity, 30d freshness | PASSING (11 tests) | none | 2026-09-16 local pytest | LOW (fail-closed, approval reset) | HIGH (stricter subset of #65 gate) | KEEP + BRIDGED (subset test in test_capability_factory) |
| DemandFactory creator_gate | MBM/DemandFactory/creator_gate.py | #65 acquisition policy, 90d max | PASSING (17 tests) | none | 2026-09-16 local pytest | LOW | HIGH (canonical policy) | KEEP (canonical) |
| Monetization router | MBM/DemandFactory/router.py | Revenue rail selection | FIXED (test assertion corrected + fallback regression) | none | 2026-09-16 local pytest | LOW (proposal-only) | HIGH | ENHANCED |
| Firecrawl adapter | MBM/Scripts/adapters/firecrawl_adapter.py | Allowlisted extraction | REAL (whitelist + REST) | FIRECRAWL_API_KEY, requests | code inspection | MEDIUM (network; allowlist enforced) | MEDIUM | KEEP (already allowlisted; registry DEFERRED until credentialed) |
| Scrapy/ragflow/openhands/langchain/fastmcp/dify/daytona/playwright_mcp adapters | MBM/Scripts/adapters/* | Various external integrations | STUB (TODO/NotImplemented) | missing creds/transports | code inspection | LOW (raise, no-op) | LOW now | RETIRE from registry (stay DEFERRED, never route) |
| GLM agents (7 files) | MBM/GLM/agents/ | Specialist workers | PRESENT, not factory-routed | agent_registry roles | directory listing | MEDIUM (unscoped if wired directly) | MEDIUM | INVESTIGATE (route only via registry/policy if revived) |
| GLM roles (23) | MBM/GLM/agent_registry.py | Role contracts | PRESENT, approval-gated writes | policy gateway | import check 2026-09-16 | LOW (all require approval for writes) | HIGH | KEEP (projected in control-plane registry) |
| LeadEngine API TODOs | MBM/LeadEngine/api/routes/*.ts | Export/LLM/BullMQ features | TODO placeholders | out of factory scope | grep | — | — | KEEP out of scope (no factory claim) |
| Clipping campaign abstraction | clipping-factory/.../campaign_abstraction.py | Adapter interface | ABSTRACT by design | concrete adapters | code inspection | LOW | — | KEEP |
| ContecRadar sources base | MBM/ContecRadar/sources/base.py | Source interface | ABSTRACT by design | github/rss adapters | code inspection | LOW | — | KEEP |
| Legacy offers (3 md) | MBM/Offers/*.md | Marketing copy | QUARANTINED (fail schema) | none | test_legacy_offer_fails | HIGH if published (fabricated claims) | — | RETIRE from release path (QUARANTINE.md) |
| .agents/skills (86 dirs) | .agents/skills/ | Domain packs | AVAILABLE, not factory-owned | per-skill | directory count | LOW (unused) | LOW for factory | KEEP as supporting (no import; factory_skills stays canonical) |

Retired/deferred items remain DENY-by-default in routing. No duplicates created:
CanonicalCreator and creator_gate are bridged by subset relation, not merged by force.

## Round 2 (2026-09-16 hardening)

| Capability | Location | Previous | New | Evidence |
|---|---|---|---|---|
| creator_qualification gate | MBM/LeadEngine/creator_qualification.py | Parallel impl outside registry | BRIDGED (3rd 30d gate, subset test) | stricter-subset test PASS |
| ProductCompiler | MBM/DemandFactory/compiler.py | Unregistered | INTEGRATED product_compile | test_compiler PASS |
| EvidenceScoring | MBM/CommercialRadar/scoring.py | Unregistered | INTEGRATED pain_scoring | test_commercial_radar PASS |
| ProductizedOffers catalog | MBM/ProductizedOffers/catalog.py | Unregistered, unapproved | INTEGRATED read-only + schema-blocked proof | catalog test + schema-block test PASS |
| OpenAIAgentAdapter | MBM/DemandFactory/adapters/openai_agent.py | Unregistered | DEFERRED (stub, no network) | code inspection + stub test PASS |
| P4 offer | productized-service/p4-lead-cleaner | Quarantine-adjacent | GRADUATED to RELEASE-CANDIDATE (publish human-gated) | test_offer_graduation PASS (real 11-row demo run) |
