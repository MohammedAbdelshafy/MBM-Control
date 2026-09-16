"""Canonical MCP capability registry (provider-neutral).

Every capability is tied to an OBSERVED tool in this OpenCode environment.
No capability is invented. Unknown provider/tool/reference = DENY.

Observed providers:
- github (MCP): issues, PRs, files, search, releases
- gitkraken (MCP): git operations + UI resources
- memory (MCP): knowledge graph
- whop (MCP): commerce (accounts/products/plans/checkout/memberships/...)
- local (built-in): filesystem, bash, playwright browser, webfetch, websearch

Permission classes (policy-neutral names, mapped to control plane):
- READ_ONLY            -> ActionClass.READ (automatic)
- SAFE_WRITE           -> ActionClass.SAFE_WRITE (automatic in scope)
- CONTROLLED_WRITE     -> ActionClass.GATED_WRITE (approval-gated)
- CONSEQUENTIAL_EXTERNAL_ACTION -> ActionClass.EXTERNAL_SIDE_EFFECT/HIGH_IMPACT
  (explicit human approval; default DENY)

Factory stages: DISCOVER, RESEARCH, SCORE, STRATEGY, BUILD, QA, PACKAGE,
RELEASE, MEASURE, LEARN. MCPs never own scoring/policy/release gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PermissionClass = Literal[
    "READ_ONLY",
    "SAFE_WRITE",
    "CONTROLLED_WRITE",
    "CONSEQUENTIAL_EXTERNAL_ACTION",
]

CapabilityStatus = Literal[
    "AVAILABLE",
    "INTEGRATED",
    "TESTED",
    "BLOCKED",
    "UNSAFE",
    "REDUNDANT",
    "DEFERRED",
]

FACTORY_STAGES = [
    "DISCOVER",
    "RESEARCH",
    "SCORE",
    "STRATEGY",
    "BUILD",
    "QA",
    "PACKAGE",
    "RELEASE",
    "MEASURE",
    "LEARN",
]


@dataclass(slots=True)
class CapabilitySpec:
    capability: str
    provider: str
    tool: str
    permission: PermissionClass
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    side_effect: str = "none"
    approval_required: bool = False
    evidence_required: bool = True
    rate_limit: str = "default"
    failure_behavior: str = "fail_closed_retry_transient_only"
    audit_fields: list[str] = field(default_factory=lambda: [
        "capability", "provider", "tool", "invocation_id", "actor",
        "timestamp", "input_hash", "output_hash", "approval_state",
        "policy_decision", "success", "artifact_ids", "error_code",
        "latency_ms", "retry_count",
    ])
    factory_stages: list[str] = field(default_factory=list)
    status: CapabilityStatus = "AVAILABLE"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _schema(required: list[str], properties: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": {k: {"type": v} for k, v in properties.items()},
    }


def build_capability_registry() -> list[CapabilitySpec]:
    """Observed-only registry. Every entry maps to a real tool."""
    return [
        # DISCOVERY / RESEARCH (read-only web)
        CapabilitySpec(
            capability="web_search", provider="local", tool="websearch",
            permission="READ_ONLY",
            input_schema=_schema(["query"], {"query": "string"}),
            output_schema=_schema([], {"results": "array"}),
            side_effect="none", approval_required=False,
            factory_stages=["DISCOVER", "RESEARCH"],
            status="INTEGRATED", reason="observed websearch tool; read-only signal collection",
        ),
        CapabilitySpec(
            capability="page_fetch", provider="local", tool="webfetch",
            permission="READ_ONLY",
            input_schema=_schema(["url"], {"url": "string"}),
            output_schema=_schema([], {"content": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["RESEARCH"],
            status="INTEGRATED", reason="observed webfetch tool; evidence gathering",
        ),
        CapabilitySpec(
            capability="document_retrieval", provider="local", tool="filesystem_read",
            permission="READ_ONLY",
            input_schema=_schema(["path"], {"path": "string"}),
            output_schema=_schema([], {"content": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["RESEARCH", "QA"],
            status="INTEGRATED", reason="observed filesystem read; artifact inspection",
        ),
        # ENGINEERING (github + gitkraken + filesystem)
        CapabilitySpec(
            capability="repository_read", provider="github", tool="github_get_file_contents",
            permission="READ_ONLY",
            input_schema=_schema(["owner", "repo"], {"owner": "string", "repo": "string", "path": "string", "ref": "string"}),
            output_schema=_schema([], {"content": "string", "sha": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["RESEARCH", "BUILD", "QA"],
            status="INTEGRATED", reason="observed github MCP file read",
        ),
        CapabilitySpec(
            capability="repository_write", provider="github", tool="github_create_or_update_file",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["owner", "repo", "path", "content", "message", "branch"], {"owner": "string", "repo": "string", "path": "string", "content": "string", "message": "string", "branch": "string"}),
            output_schema=_schema([], {"commit_sha": "string"}),
            side_effect="remote_branch_mutation", approval_required=True,
            factory_stages=["BUILD", "PACKAGE"],
            status="INTEGRATED", reason="observed github MCP write; approval-gated, never auto-publish",
        ),
        CapabilitySpec(
            capability="issue_management", provider="github", tool="github_issue_write",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["owner", "repo", "method"], {"owner": "string", "repo": "string", "method": "string"}),
            output_schema=_schema([], {"issue_number": "string"}),
            side_effect="remote_issue_mutation", approval_required=True,
            factory_stages=["MEASURE", "LEARN"],
            status="INTEGRATED", reason="observed github issue write; evidence updates only with factual results",
        ),
        CapabilitySpec(
            capability="pull_request_management", provider="github", tool="github_create_pull_request",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["owner", "repo", "title", "head", "base"], {"owner": "string", "repo": "string", "title": "string", "head": "string", "base": "string"}),
            output_schema=_schema([], {"pull_number": "string"}),
            side_effect="remote_pr_creation", approval_required=True,
            factory_stages=["PACKAGE", "RELEASE"],
            status="INTEGRATED", reason="observed github PR create; proposal-only, human merges",
        ),
        CapabilitySpec(
            capability="code_context_lookup", provider="github", tool="github_search_code",
            permission="READ_ONLY",
            input_schema=_schema(["query"], {"query": "string"}),
            output_schema=_schema([], {"results": "array"}),
            side_effect="none", approval_required=False,
            factory_stages=["DISCOVER", "RESEARCH", "BUILD"],
            status="INTEGRATED", reason="observed github code search",
        ),
        CapabilitySpec(
            capability="version_control", provider="gitkraken", tool="GitKraken_git_log_or_diff",
            permission="READ_ONLY",
            input_schema=_schema(["directory", "action"], {"directory": "string", "action": "string"}),
            output_schema=_schema([], {"output": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["QA", "MEASURE"],
            status="INTEGRATED", reason="observed gitkraken git log/diff; ancestry verification",
        ),
        CapabilitySpec(
            capability="branch_isolation", provider="gitkraken", tool="GitKraken_git_worktree",
            permission="SAFE_WRITE",
            input_schema=_schema(["directory", "action"], {"directory": "string", "action": "string"}),
            output_schema=_schema([], {"worktree": "string"}),
            side_effect="local_worktree", approval_required=False,
            factory_stages=["BUILD", "QA"],
            status="INTEGRATED", reason="observed gitkraken worktree; risky work isolation",
        ),
        CapabilitySpec(
            capability="test_execution", provider="local", tool="bash",
            permission="SAFE_WRITE",
            input_schema=_schema(["command"], {"command": "string"}),
            output_schema=_schema([], {"exit_code": "string"}),
            side_effect="local_process", approval_required=False,
            rate_limit="serial_hermetic_only",
            factory_stages=["QA"],
            status="INTEGRATED", reason="observed bash; hermetic pytest only, no external mutation",
        ),
        CapabilitySpec(
            capability="browser_testing", provider="local", tool="playwright_browser_snapshot",
            permission="READ_ONLY",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"snapshot": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["QA"],
            status="INTEGRATED", reason="observed playwright snapshot; read-only checks",
        ),
        # DATA / CRM (whop commerce — consequential)
        CapabilitySpec(
            capability="storefront_lookup", provider="whop", tool="whop-products_get",
            permission="READ_ONLY",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"product": "object"}),
            side_effect="none", approval_required=False,
            factory_stages=["RESEARCH", "MEASURE"],
            status="INTEGRATED", reason="observed whop product read surface",
        ),
        CapabilitySpec(
            capability="checkout_configuration", provider="whop", tool="whop-checkout-configurations_create",
            permission="CONSEQUENTIAL_EXTERNAL_ACTION",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"checkout_url": "string"}),
            side_effect="commercial_commitment", approval_required=True,
            factory_stages=["PACKAGE", "RELEASE"],
            status="BLOCKED", reason="consequential commercial action; human-controlled, not auto-executed",
        ),
        CapabilitySpec(
            capability="payout_execution", provider="whop", tool="whop-payouts_create",
            permission="CONSEQUENTIAL_EXTERNAL_ACTION",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"payout_id": "string"}),
            side_effect="money_movement", approval_required=True,
            factory_stages=[],
            status="UNSAFE", reason="money movement never auto-executed by Factory",
        ),
        # KNOWLEDGE
        CapabilitySpec(
            capability="knowledge_graph", provider="memory", tool="memory_read_graph",
            permission="READ_ONLY",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"graph": "object"}),
            side_effect="none", approval_required=False,
            factory_stages=["RESEARCH", "LEARN"],
            status="INTEGRATED", reason="observed memory MCP graph read",
        ),
        # OPERATIONS (scheduled execution guarded)
        CapabilitySpec(
            capability="workflow_execution", provider="gitkraken", tool="GitKraken_git_status",
            permission="READ_ONLY",
            input_schema=_schema(["directory"], {"directory": "string"}),
            output_schema=_schema([], {"status": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["MEASURE"],
            status="INTEGRATED", reason="observed git status; pre-flight verification",
        ),
        # DEFERRED: ecosystem CLIs requiring credentials / transports not observed here
        CapabilitySpec(
            capability="copy_generation", provider="ecosystem", tool="gemini_cli_adapter",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["prompt"], {"prompt": "string"}),
            output_schema=_schema([], {"text": "string"}),
            side_effect="external_llm_call", approval_required=True,
            factory_stages=["STRATEGY", "BUILD"],
            status="DEFERRED", reason="CLI not authenticated in this environment; needs GOOGLE_API_KEY + human approval",
        ),
        CapabilitySpec(
            capability="video_generation", provider="ecosystem", tool="higgsfield_adapter",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["brief"], {"brief": "string"}),
            output_schema=_schema([], {"asset": "object"}),
            side_effect="external_media_cost", approval_required=True,
            factory_stages=["BUILD"],
            status="DEFERRED", reason="no authenticated Higgsfield provider here; brief-only adapter retained",
        ),
        CapabilitySpec(
            capability="company_enrichment", provider="ecosystem", tool="hubspot_adapter",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["domain"], {"domain": "string"}),
            output_schema=_schema([], {"company": "object"}),
            side_effect="external_crm_write", approval_required=True,
            factory_stages=["RESEARCH"],
            status="DEFERRED", reason="proposal-only HubSpot adapter; no credentials, no auto-mutation",
        ),
        # CONVERGED (Phase 4): control-plane bus + factory-native deterministic gates.
        # All observed with hermetic tests; no external side effects.
        CapabilitySpec(
            capability="dialer_eligibility", provider="control-plane", tool="dialer_eligibility_filter",
            permission="READ_ONLY",
            input_schema=_schema(["leads"], {"leads": "array"}),
            output_schema=_schema([], {"eligible": "array"}),
            side_effect="none", approval_required=False,
            factory_stages=["SCORE", "QA"],
            status="INTEGRATED", reason="jarvis_control_plane/capabilities.py wraps dialer_verification_gate; hermetic",
        ),
        CapabilitySpec(
            capability="suppression_check", provider="control-plane", tool="suppression_check",
            permission="READ_ONLY",
            input_schema=_schema([], {"phone": "string", "email": "string"}),
            output_schema=_schema([], {"suppressed": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["SCORE", "QA"],
            status="INTEGRATED", reason="read-only DNC/suppression verdict; hermetic",
        ),
        CapabilitySpec(
            capability="provider_status", provider="control-plane", tool="phound_status",
            permission="READ_ONLY",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"status": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["MEASURE"],
            status="INTEGRATED", reason="UI-safe status, credentials redacted upstream",
        ),
        CapabilitySpec(
            capability="browser_extract_allowlisted", provider="control-plane", tool="browser_navigate_extract",
            permission="READ_ONLY",
            input_schema=_schema(["url"], {"url": "string"}),
            output_schema=_schema([], {"content": "string"}),
            side_effect="none", approval_required=False,
            rate_limit="allowlist_only_example_github_zillow",
            factory_stages=["RESEARCH", "QA"],
            status="INTEGRATED", reason="allowlisted read-only extraction; injection-guarded; hermetic via fetcher injection",
        ),
        CapabilitySpec(
            capability="creator_evidence_gate", provider="factory", tool="creator_gate.evaluate_creator_evidence",
            permission="READ_ONLY",
            input_schema=_schema(["platform", "profile", "audience_count", "evidence_url", "timestamp"], {"platform": "string", "profile": "string", "audience_count": "string", "evidence_url": "string", "timestamp": "string"}),
            output_schema=_schema([], {"status": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["SCORE", "STRATEGY"],
            status="INTEGRATED", reason="MBM/DemandFactory/creator_gate.py; 20k deterministic; LeadEngine CanonicalCreator (30d) is stricter subset, bridged not duplicated",
        ),
        CapabilitySpec(
            capability="offer_validation", provider="factory", tool="offer_schema.validate_offer",
            permission="READ_ONLY",
            input_schema=_schema(["offer_id"], {"offer_id": "string"}),
            output_schema=_schema([], {"ready": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["STRATEGY", "QA"],
            status="INTEGRATED", reason="MBM/Offers/offer_schema.py evidence-first; fabricated-claim gates",
        ),
        CapabilitySpec(
            capability="radar_slice_a", provider="factory", tool="slice_a.run_slice_a",
            permission="READ_ONLY",
            input_schema=_schema(["signals"], {"signals": "array"}),
            output_schema=_schema([], {"opportunities": "array"}),
            side_effect="none", approval_required=False,
            factory_stages=["DISCOVER", "RESEARCH", "SCORE"],
            status="INTEGRATED", reason="MBM/ContecRadar/slice_a.py offline only; exclusions fail-closed",
        ),
        # REVIVED ROUND 2: parallel-session modules, observed + tested.
        CapabilitySpec(
            capability="product_compile", provider="factory", tool="compiler.ProductCompiler.compile",
            permission="READ_ONLY",
            input_schema=_schema(["product_id"], {"product_id": "string"}),
            output_schema=_schema([], {"plan_hash": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["BUILD", "QA"],
            status="INTEGRATED", reason="MBM/DemandFactory/compiler.py deterministic plan + hash; dry_run default; unsafe perms denied",
        ),
        CapabilitySpec(
            capability="pain_scoring", provider="factory", tool="EvidenceScoring.score_candidate",
            permission="READ_ONLY",
            input_schema=_schema(["candidate_id"], {"candidate_id": "string"}),
            output_schema=_schema([], {"score": "string"}),
            side_effect="none", approval_required=False,
            factory_stages=["SCORE", "MEASURE", "LEARN"],
            status="INTEGRATED", reason="MBM/CommercialRadar/scoring.py event-sourced decay + cap; ContecRadar kept for DISCOVER (distinct models)",
        ),
        CapabilitySpec(
            capability="offer_catalog_lookup", provider="factory", tool="catalog.get_catalog",
            permission="READ_ONLY",
            input_schema=_schema([], {}),
            output_schema=_schema([], {"offers": "array"}),
            side_effect="none", approval_required=False,
            factory_stages=["STRATEGY", "MEASURE"],
            status="INTEGRATED", reason="MBM/ProductizedOffers/catalog.py read-only; entries must still pass offer_schema before release",
        ),
        CapabilitySpec(
            capability="agent_assembly", provider="ecosystem", tool="OpenAIAgentAdapter.execute",
            permission="CONTROLLED_WRITE",
            input_schema=_schema(["plan_id"], {"plan_id": "string"}),
            output_schema=_schema([], {"assets": "array"}),
            side_effect="stub_only_no_external_call", approval_required=True,
            factory_stages=["BUILD"],
            status="DEFERRED", reason="hermetic stub today (stub_asset_for_*); live SDK wiring needs credentials + approval",
        ),
    ]


def permission_to_action_class(permission: PermissionClass) -> str:
    return {
        "READ_ONLY": "READ",
        "SAFE_WRITE": "SAFE_WRITE",
        "CONTROLLED_WRITE": "GATED_WRITE",
        "CONSEQUENTIAL_EXTERNAL_ACTION": "EXTERNAL_SIDE_EFFECT",
    }[permission]


def unknown_capability_denied(name: str, registry: list[CapabilitySpec]) -> bool:
    """Default-unknown = DENY. Returns True when denied."""
    known = {c.capability for c in registry}
    return name not in known


def coverage_report(registry: list[CapabilitySpec]) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {
        "AVAILABLE": [], "INTEGRATED": [], "TESTED": [],
        "BLOCKED": [], "UNSAFE": [], "REDUNDANT": [], "DEFERRED": [],
    }
    for spec in registry:
        report[spec.status].append(f"{spec.capability} ({spec.provider}:{spec.tool})")
    # TESTED = INTEGRATED capabilities covered by hermetic tests in this repo.
    tested = {
        "web_search", "page_fetch", "document_retrieval", "repository_read",
        "repository_write", "issue_management", "pull_request_management",
        "code_context_lookup", "version_control", "branch_isolation",
        "test_execution", "browser_testing", "storefront_lookup",
        "knowledge_graph", "workflow_execution",
        "dialer_eligibility", "suppression_check", "provider_status",
        "browser_extract_allowlisted", "creator_evidence_gate",
        "offer_validation", "radar_slice_a",
        "product_compile", "pain_scoring", "offer_catalog_lookup",
    }
    report["TESTED"] = sorted(tested)
    return report
