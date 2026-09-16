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
| checkout_configuration | whop | whop-checkout-configurations_create | PACKAGE, RELEASE | CONSEQUENTIAL_EXTERNAL_ACTION | yes | commercial_commitment | BLOCKED |
| payout_execution | whop | whop-payouts_create | — | CONSEQUENTIAL_EXTERNAL_ACTION | yes | money_movement | UNSAFE |
| knowledge_graph | memory | memory_read_graph | RESEARCH, LEARN | READ_ONLY | no | none | INTEGRATED |
| workflow_execution | gitkraken | GitKraken_git_status | MEASURE | READ_ONLY | no | none | INTEGRATED |
| copy_generation | ecosystem | gemini_cli_adapter | STRATEGY, BUILD | CONTROLLED_WRITE | yes | external_llm_call | DEFERRED |
| video_generation | ecosystem | higgsfield_adapter | BUILD | CONTROLLED_WRITE | yes | external_media_cost | DEFERRED |
| company_enrichment | ecosystem | hubspot_adapter | RESEARCH | CONTROLLED_WRITE | yes | external_crm_write | DEFERRED |

## Policy mapping

- READ_ONLY → `ActionClass.READ` (automatic)
- SAFE_WRITE → `ActionClass.SAFE_WRITE` (automatic in scope)
- CONTROLLED_WRITE → `ActionClass.GATED_WRITE` (approval-gated)
- CONSEQUENTIAL_EXTERNAL_ACTION → `ActionClass.EXTERNAL_SIDE_EFFECT` (human approval; default DENY)

## Coverage

- AVAILABLE: all rows above
- INTEGRATED: 22 read/safe/controlled capabilities with hermetic tests
- TESTED: 22 (see `jarvis_control_plane/tests/test_capability_factory.py` + control-plane suites)
- BLOCKED: checkout_configuration (commercial commitment, human-controlled)
- UNSAFE: payout_execution (money movement, never auto-executed)
- REDUNDANT: none (one canonical contract per function)
- DEFERRED: copy_generation, video_generation, company_enrichment (needs credentials/transport not observed here)

## Go-live rule

A capability may be used in production only when registered, schema-validated,
policy-defined, authorized, failure-defined, evidence-defined, tested, CI green,
and side effects gated. Unknown/partial stays disabled.
