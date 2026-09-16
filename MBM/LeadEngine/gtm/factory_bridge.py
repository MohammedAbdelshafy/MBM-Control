"""GTM factory bridge — convergence map from mission roles to real systems.

Every mission role resolves to OBSERVED implementations only. Agent contracts
whose handlers are PROCESSED_STUB are NEVER routed as executable; they are
marked DEFERRED with the real (tested) alternative in wired_via.

Statuses: WIRED (deterministic + tested) | DEFERRED (needs real handler,
credentials, or authorized source) | BLOCKED (consequential; human approval
+ production gate, never automatic).

Unknown role -> KeyError (fail-closed, same as unknown capability -> DENY).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RoleStatus = Literal["WIRED", "DEFERRED", "BLOCKED"]


@dataclass(slots=True)
class MissionRoleBinding:
    role: str
    status: RoleStatus
    existing_agents: list[str] = field(default_factory=list)
    wired_via: list[str] = field(default_factory=list)
    permission: str = "READ_ONLY"
    approval_required: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_MISSION_ROLES: dict[str, MissionRoleBinding] = {
    "gtm_strategist": MissionRoleBinding(
        role="gtm_strategist", status="WIRED",
        existing_agents=["GTM_COMMANDER"],
        wired_via=["MBM.LeadEngine.gtm.gtm_commander (dry_run default)",
                   "MBM.DemandFactory.engine.DemandFactory"],
        permission="READ_ONLY", reason="strategy is proposal-only; execution via factory engine gates",
    ),
    "market_research": MissionRoleBinding(
        role="market_research", status="WIRED",
        existing_agents=["RADAR", "SOCIAL_LISTENER", "NEWS_MONITOR"],
        wired_via=["MBM.ContecRadar.slice_a.run_slice_a (offline, tested)",
                   "websearch/webfetch tools (read-only)"],
        permission="READ_ONLY",
        reason="agent contracts are PROCESSED_STUB (no registered handlers); real discovery flows through slice_a + read tools",
    ),
    "icp_definition": MissionRoleBinding(
        role="icp_definition", status="WIRED",
        existing_agents=[],
        wired_via=["MBM.LeadEngine.gtm.guarded_actions.score_account (transparent factors)",
                   "MBM.Offers.offer_schema buyer_segment contract"],
        permission="READ_ONLY", reason="no ICP-defining agent exists; criteria live in code + offer schema, scored transparently",
    ),
    "prospect_discovery": MissionRoleBinding(
        role="prospect_discovery", status="DEFERRED",
        existing_agents=["INTENT_HUNTER", "FACEBOOK_INTEL"],
        wired_via=[],
        permission="READ_ONLY",
        reason="contracts are stubs; no authorized prospect source wired (fixtures only until a source is approved)",
    ),
    "company_research": MissionRoleBinding(
        role="company_research", status="WIRED",
        existing_agents=["ACCOUNT_RESEARCHER"],
        wired_via=["webfetch/page_fetch + browser_extract_allowlisted (allowlisted, tested)"],
        permission="READ_ONLY",
        reason="agent contract is a stub; real research flows through allowlisted read tools with provenance required downstream",
    ),
    "lead_qualification": MissionRoleBinding(
        role="lead_qualification", status="WIRED",
        existing_agents=["QUALIFIER"],
        wired_via=["MBM.LeadEngine.gtm.production_gate.ProductionGate.evaluate_gate (6-point, tested)",
                   "MBM.LeadEngine.dialer_verification_gate",
                   "jarvis_control_plane suppression_check"],
        permission="READ_ONLY",
        reason="QUALIFIER contract is a stub; real qualification is the production gate + verification gate + suppression",
    ),
    "lead_cleaning": MissionRoleBinding(
        role="lead_cleaning", status="WIRED",
        existing_agents=[],
        wired_via=["productized-service p4 clean_leads.run_cleaner (canonical gate, demo-verified)",
                   "MBM.LeadEngine.gtm.guarded_actions.dedupe_prospects"],
        permission="SAFE_WRITE", reason="scoped reversible artifacts only (cleaned.csv/summary/report)",
    ),
    "account_scoring": MissionRoleBinding(
        role="account_scoring", status="WIRED",
        existing_agents=["QUALIFIER"],
        wired_via=["MBM.LeadEngine.gtm.guarded_actions.score_account (explained factors)",
                   "MBM.CommercialRadar.scoring.EvidenceScoring (decay + cap)"],
        permission="READ_ONLY", reason="scores are advisory; never auto-qualify (thresholds explicit)",
    ),
    "offer_matching": MissionRoleBinding(
        role="offer_matching", status="WIRED",
        existing_agents=["AI_FIT_ARCHITECT"],
        wired_via=["MBM.DemandFactory.router.choose_revenue_route (proposal-only, tested)"],
        permission="READ_ONLY", reason="agent contract is a stub; real matching is the revenue router",
    ),
    "copy_generation": MissionRoleBinding(
        role="copy_generation", status="WIRED",
        existing_agents=["PERSONALIZER"],
        wired_via=["MBM.LeadEngine.gtm.guarded_actions.draft_outreach (banned-claim fail-closed, tested)"],
        permission="SAFE_WRITE", reason="drafts only (draft_pending_review); PERSONALIZER contract is a stub",
    ),
    "outreach_send": MissionRoleBinding(
        role="outreach_send", status="BLOCKED",
        existing_agents=["EMAIL_DISPATCHER", "VOICE_AGENT"],
        wired_via=["MBM.LeadEngine.gtm.gmail_dispatcher (DRY-RUN default, gate-enforced)",
                   "MBM.LeadEngine.gtm.production_gate HUMAN_APPROVED"],
        permission="CONSEQUENTIAL_EXTERNAL_ACTION", approval_required=True,
        reason="sending needs production-gate HUMAN_APPROVED + credentials; never automatic; no creds observed here",
    ),
    "response_handling": MissionRoleBinding(
        role="response_handling", status="WIRED",
        existing_agents=["CONVERSATION_AGENT"],
        wired_via=["MBM.LeadEngine.gtm.guarded_actions.response_classifier (deterministic labels, tested)"],
        permission="READ_ONLY",
        reason="agent contract is a stub; UNSUBSCRIBE routes to immediate suppression",
    ),
    "sales_assistant": MissionRoleBinding(
        role="sales_assistant", status="WIRED",
        existing_agents=["DEAL_STRATEGIST", "MEETING_AGENT", "OBJECTION_AGENT"],
        wired_via=["MBM.LeadEngine.gtm.guarded_actions.build_sales_brief (verified fields only)"],
        permission="READ_ONLY",
        reason="agent contracts are stubs; briefs compose evidence only, no commitments (next_action is human_review)",
    ),
    "crm": MissionRoleBinding(
        role="crm", status="WIRED",
        existing_agents=["REVOPS_AGENT"],
        wired_via=["MBM.LeadEngine.gtm.adapters.CRMAdapter (overlay, never mutates production CRM)",
                   "MBM.LeadEngine.gtm.guarded_actions.crm_overlay_proposal"],
        permission="CONTROLLED_WRITE", approval_required=True,
        reason="proposal-only; HubSpot/Airtable/Notion/Supabase MCPs not observed here (DEFERRED until credentialed)",
    ),
    "pipeline": MissionRoleBinding(
        role="pipeline", status="WIRED",
        existing_agents=["GTM_COMMANDER"],
        wired_via=["MBM.LeadEngine.gtm.state_machine.GtmStateMachine (14 states, validated transitions)"],
        permission="CONTROLLED_WRITE", approval_required=True,
        reason="in-memory state; terminal commercial moves still require approval downstream",
    ),
    "analytics": MissionRoleBinding(
        role="analytics", status="WIRED",
        existing_agents=["REVOPS_AGENT", "ATTRIBUTION_AGENT", "LEARNING_AGENT"],
        wired_via=["MBM.LeadEngine.gtm.scoreboard (existing tests)",
                   "MBM.LeadEngine.gtm.attribution (journey tracking)"],
        permission="READ_ONLY", reason="measured events only; metrics never fabricated (zero dashboard)",
    ),
}

# Mission roles that must NEVER execute automatically, even if wired.
_NEVER_AUTOMATIC = {"outreach_send"}

# Explicitly retired from routing (evidence-first violations by construction).
_RETIRED = {
    "ROI_AGENT": "fabricated ROI/savings projections violate the evidence-first contract (see offer_schema FABRICATED_ROI)",
}


def get_binding(role: str) -> MissionRoleBinding:
    """Return one role binding. Unknown role -> KeyError (fail-closed)."""
    if role not in _MISSION_ROLES:
        raise KeyError(f"unknown GTM mission role denied: {role}")
    return _MISSION_ROLES[role]


def list_bindings() -> list[MissionRoleBinding]:
    return list(_MISSION_ROLES.values())


def wired_roles() -> list[str]:
    return [role for role, binding in _MISSION_ROLES.items() if binding.status == "WIRED"]


def blocked_roles() -> list[str]:
    return [role for role, binding in _MISSION_ROLES.items()
            if binding.status == "BLOCKED" or role in _NEVER_AUTOMATIC]


def retired_agents() -> dict[str, str]:
    return dict(_RETIRED)


# Mission pipeline (Part 3) mapped onto the real GtmState machine.
# Stages without a GtmState equivalent stay proposal-level (no state write).
PIPELINE_TO_STATE: dict[str, str] = {
    "MARKET_SIGNAL": "DISCOVERED",
    "RESEARCH": "DISCOVERED",
    "ICP": "DISCOVERED",
    "PROSPECT_DISCOVERY": "DISCOVERED",
    "EVIDENCE_ENRICHMENT": "QUALIFYING",
    "QUALIFICATION": "QUALIFYING",
    "SCORING": "QUALIFYING",
    "OFFER_MATCH": "QUALIFIED",
    "MESSAGE_DRAFT": "QUALIFIED",
    "HUMAN_REVIEW": "QUALIFIED",
    "OUTREACH": "CONTACTING",
    "RESPONSE": "ENGAGED",
    "CRM": "ENGAGED",
    "FOLLOW_UP": "ENGAGED",
    "MEASURE": "ENGAGED",
    "LEARN": "NURTURE",
}


def pipeline_state(pipeline_stage: str) -> str:
    if pipeline_stage not in PIPELINE_TO_STATE:
        raise KeyError(f"unknown GTM pipeline stage denied: {pipeline_stage}")
    return PIPELINE_TO_STATE[pipeline_stage]
