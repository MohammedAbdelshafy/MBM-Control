# MCP Capability Matrix (observed only)

Generated from `jarvis_control_plane/capability_registry.py`.
Every capability tied to an observed tool. Unknown = DENY.

| Capability | Provider | Tool | Factory Stages | Permission | Approval | Side effect | Status |
|---|---|---|---|---|---|---|---|
| web_search | local | websearch | DISCOVER, RESEARCH | READ_ONLY | no | none | INTEGRATED |
| page_fetch | local | webfetch | RESEARCH | READ_ONLY | no | none | INTEGRATED |
| document_retrieval | local | filesystem_read | RESEARCH, QA | READ_ONLY | no | none | INTEGRATED |
| repository_read | github | github_get_file_contents | RESEARCH, BUILD, QA | READ_ONLY | no | none | INTEGRATED |
| repository_write | github | github_create_or_update_file | BUILD, PACKAGE | CONTROLLED_WRITE | yes | remote_branch_mutation | INTEGRATED |
| issue_management | github | github_issue_write | MEASURE, LEARN | CONTROLLED_WRITE | yes | remote_issue_mutation | INTEGRATED |
| pull_request_management | github | github_create_pull_request | PACKAGE, RELEASE | CONTROLLED_WRITE | yes | remote_pr_creation | INTEGRATED |
| code_context_lookup | github | github_search_code | DISCOVER, RESEARCH, BUILD | READ_ONLY | no | none | INTEGRATED |
| version_control | gitkraken | GitKraken_git_log_or_diff | QA, MEASURE | READ_ONLY | no | none | INTEGRATED |
| branch_isolation | gitkraken | GitKraken_git_worktree | BUILD, QA | SAFE_WRITE | no | local_worktree | INTEGRATED |
| test_execution | local | bash | QA | SAFE_WRITE | no | local_process | INTEGRATED |
| browser_testing | local | playwright_browser_snapshot | QA | READ_ONLY | no | none | INTEGRATED |
| storefront_lookup | whop | whop-products_get | RESEARCH, MEASURE | READ_ONLY | no | none | INTEGRATED |
| dialer_eligibility | control-plane | dialer_eligibility_filter | SCORE, QA | READ_ONLY | no | none | INTEGRATED |
| suppression_check | control-plane | suppression_check | SCORE, QA | READ_ONLY | no | none | INTEGRATED |
| provider_status | control-plane | phound_status | MEASURE | READ_ONLY | no | none | INTEGRATED |
| browser_extract_allowlisted | control-plane | browser_navigate_extract | RESEARCH, QA | READ_ONLY | no | none | INTEGRATED |
| creator_evidence_gate | factory | creator_gate.evaluate_creator_evidence | SCORE, STRATEGY | READ_ONLY | no | none | INTEGRATED |
| offer_validation | factory | offer_schema.validate_offer | STRATEGY, QA | READ_ONLY | no | none | INTEGRATED |
| radar_slice_a | factory | slice_a.run_slice_a | DISCOVER, RESEARCH, SCORE | READ_ONLY | no | none | INTEGRATED |
| product_compile | factory | compiler.ProductCompiler.compile | BUILD, QA | READ_ONLY | no | none | INTEGRATED |
| pain_scoring | factory | EvidenceScoring.score_candidate | SCORE, MEASURE, LEARN | READ_ONLY | no | none | INTEGRATED |
| offer_catalog_lookup | factory | catalog.get_catalog | STRATEGY, MEASURE | READ_ONLY | no | none | INTEGRATED |
| agent_assembly | ecosystem | OpenAIAgentAdapter.execute | BUILD | CONTROLLED_WRITE | yes | stub_only_no_external_call | DEFERRED |
| checkout_configuration | whop | whop-checkout-configurations_create | PACKAGE, RELEASE | CONSEQUENTIAL_EXTERNAL_ACTION | yes | commercial_commitment | BLOCKED |
| payout_execution | whop | whop-payouts_create | — | CONSEQUENTIAL_EXTERNAL_ACTION | yes | money_movement | UNSAFE |
| knowledge_graph | memory | memory_read_graph | RESEARCH, LEARN | READ_ONLY | no | none | INTEGRATED |
| workflow_execution | gitkraken | GitKraken_git_status | MEASURE | READ_ONLY | no | none | INTEGRATED |
| copy_generation | ecosystem | gemini_cli_adapter | STRATEGY, BUILD | CONTROLLED_WRITE | yes | external_llm_call | DEFERRED |
| video_generation | ecosystem | higgsfield_adapter | BUILD | CONTROLLED_WRITE | yes | external_media_cost | DEFERRED |
| company_enrichment | ecosystem | hubspot_adapter | RESEARCH | CONTROLLED_WRITE | yes | external_crm_write | DEFERRED |
| market_research | gtm | slice_a.run_slice_a | DISCOVER, RESEARCH | READ_ONLY | no | none | INTEGRATED |
| company_research | gtm | webfetch | RESEARCH | READ_ONLY | no | none | INTEGRATED |
| prospect_discovery | gtm | fixtures_only | DISCOVER | READ_ONLY | no | none | DEFERRED |
| lead_enrichment | gtm | fixtures_only | RESEARCH | READ_ONLY | no | none | DEFERRED |
| lead_cleaning | gtm | run_cleaner | SCORE | SAFE_WRITE | no | scoped_artifact_write | INTEGRATED |
| lead_qualification | gtm | production_gate.evaluate_gate | SCORE | READ_ONLY | no | none | INTEGRATED |
| account_scoring | gtm | score_account | SCORE | READ_ONLY | no | none | INTEGRATED |
| offer_matching | gtm | choose_revenue_route | STRATEGY | READ_ONLY | no | none | INTEGRATED |
| message_generation | gtm | draft_outreach | STRATEGY, BUILD | SAFE_WRITE | no | draft_artifact | INTEGRATED |
| outreach_drafting | gtm | crm_overlay_proposal | PACKAGE | CONTROLLED_WRITE | yes | proposal_artifact | INTEGRATED |
| outreach_send | gtm | gmail_dispatcher | — | CONSEQUENTIAL_EXTERNAL_ACTION | yes | external_send | BLOCKED |
| response_classification | gtm | response_classifier | MEASURE | READ_ONLY | no | none | INTEGRATED |
| crm_update | gtm | crm_overlay_proposal | MEASURE, LEARN | CONTROLLED_WRITE | yes | proposal_only_no_mutation | INTEGRATED |
| pipeline_management | gtm | GtmStateMachine.transition | MEASURE | CONTROLLED_WRITE | yes | in_memory_state | INTEGRATED |
| sales_brief | gtm | build_sales_brief | STRATEGY | READ_ONLY | no | none | INTEGRATED |
| gtm_analytics | gtm | scoreboard | MEASURE, LEARN | READ_ONLY | no | none | INTEGRATED |

## Policy mapping

- READ_ONLY → `ActionClass.READ` (automatic)
- SAFE_WRITE → `ActionClass.SAFE_WRITE` (automatic in scope)
- CONTROLLED_WRITE → `ActionClass.GATED_WRITE` (approval-gated)
- CONSEQUENTIAL_EXTERNAL_ACTION → `ActionClass.EXTERNAL_SIDE_EFFECT` (human approval; default DENY)

## Coverage

- AVAILABLE: all rows above
- INTEGRATED: 38 read/safe/controlled capabilities with hermetic tests
- TESTED: 38 (see `jarvis_control_plane/tests/test_capability_factory.py`, `MBM/LeadEngine/tests/test_gtm_factory_bridge.py` + control-plane suites)
- BLOCKED: checkout_configuration (commercial commitment), outreach_send (external send; needs production-gate HUMAN_APPROVED + credentials)
- UNSAFE: payout_execution (money movement, never auto-executed)
- REDUNDANT: none (one canonical contract per function; GTM reuses factory/control-plane tools, no second registry)
- DEFERRED: copy_generation, video_generation, company_enrichment, agent_assembly, prospect_discovery, lead_enrichment (needs credentials/transport/authorized source not observed here; stubs and fixtures never route — router denies DEFERRED)

## Go-live rule

A capability may be used in production only when registered, schema-validated,
policy-defined, authorized, failure-defined, evidence-defined, tested, CI green,
and side effects gated. Unknown/partial stays disabled.
