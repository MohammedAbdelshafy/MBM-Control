"""
GTM AGENT REGISTRY
=============================================================================
Defines the 26-agent GTM swarm contracts, capabilities, and dispatch interfaces.

Agents:
  RADAR, INTENT_HUNTER, SOCIAL_LISTENER, ACCOUNT_RESEARCHER, BUYER_MAPPER,
  PAIN_MINER, AI_FIT_ARCHITECT, ROI_AGENT, QUALIFIER, PERSONALIZER,
  CHANNEL_ROUTER, VOICE_AGENT, CONVERSATION_AGENT, IDENTITY_AGENT,
  MEETING_AGENT, FOLLOWUP_AGENT, OBJECTION_AGENT, DEAL_STRATEGIST,
  REVOPS_AGENT, ATTRIBUTION_AGENT, EXPERIMENT_AGENT, LEARNING_AGENT,
  GTM_COMMANDER, EMAIL_DISPATCHER, FACEBOOK_INTEL, NEWS_MONITOR
=============================================================================
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone


class AgentRole(str, Enum):
    RADAR = "RADAR"
    INTENT_HUNTER = "INTENT_HUNTER"
    SOCIAL_LISTENER = "SOCIAL_LISTENER"
    ACCOUNT_RESEARCHER = "ACCOUNT_RESEARCHER"
    BUYER_MAPPER = "BUYER_MAPPER"
    PAIN_MINER = "PAIN_MINER"
    AI_FIT_ARCHITECT = "AI_FIT_ARCHITECT"
    ROI_AGENT = "ROI_AGENT"
    QUALIFIER = "QUALIFIER"
    PERSONALIZER = "PERSONALIZER"
    CHANNEL_ROUTER = "CHANNEL_ROUTER"
    VOICE_AGENT = "VOICE_AGENT"
    CONVERSATION_AGENT = "CONVERSATION_AGENT"
    IDENTITY_AGENT = "IDENTITY_AGENT"
    MEETING_AGENT = "MEETING_AGENT"
    FOLLOWUP_AGENT = "FOLLOWUP_AGENT"
    OBJECTION_AGENT = "OBJECTION_AGENT"
    DEAL_STRATEGIST = "DEAL_STRATEGIST"
    REVOPS_AGENT = "REVOPS_AGENT"
    ATTRIBUTION_AGENT = "ATTRIBUTION_AGENT"
    EXPERIMENT_AGENT = "EXPERIMENT_AGENT"
    LEARNING_AGENT = "LEARNING_AGENT"
    GTM_COMMANDER = "GTM_COMMANDER"
    # Expanded scope: email, Facebook, Google News
    EMAIL_DISPATCHER = "EMAIL_DISPATCHER"
    FACEBOOK_INTEL = "FACEBOOK_INTEL"
    NEWS_MONITOR = "NEWS_MONITOR"


class GtmAgentContract:
    """Explicit contract definition for a GTM agent."""

    def __init__(
        self,
        role: AgentRole,
        name: str,
        description: str,
        input_types: List[str],
        output_types: List[str],
        handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        is_active: bool = True,
    ):
        self.role = role
        self.name = name
        self.description = description
        self.input_types = input_types
        self.output_types = output_types
        self.handler = handler or self._default_handler
        self.is_active = is_active

    def _default_handler(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Default stub handler honoring the contract."""
        return {
            "agent": self.role.value,
            "status": "PROCESSED_STUB",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs_received": list(inputs.keys()),
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent handler safely with error boundary."""
        if not self.is_active:
            return {"agent": self.role.value, "status": "INACTIVE"}
        try:
            return self.handler(inputs)
        except Exception as e:
            return {"agent": self.role.value, "status": "ERROR", "error": str(e)}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "is_active": self.is_active,
        }


class AgentRegistry:
    """Central registry managing all 26 GTM agent contracts and routing."""

    def __init__(self):
        self._agents: Dict[AgentRole, GtmAgentContract] = {}
        self._initialize_default_registry()

    def _initialize_default_registry(self) -> None:
        """Register the 26 standard GTM agent contracts."""
        contracts = [
            GtmAgentContract(
                role=AgentRole.RADAR,
                name="Market Radar",
                description="Scans macro market shifts, hiring sprees, and new company formations.",
                input_types=["geography", "verticals"],
                output_types=["market_signals"],
            ),
            GtmAgentContract(
                role=AgentRole.INTENT_HUNTER,
                name="Buyer Intent Hunter",
                description="Discovers active hiring bottlenecks and public requests for AI automation.",
                input_types=["signals", "social_posts", "job_postings"],
                output_types=["scored_prospects", "intent_signals"],
            ),
            GtmAgentContract(
                role=AgentRole.SOCIAL_LISTENER,
                name="Social Listener",
                description="Monitors Reddit, LinkedIn, and contractor forums for operational complaints.",
                input_types=["keywords", "subreddits", "groups"],
                output_types=["conversational_threads"],
            ),
            GtmAgentContract(
                role=AgentRole.ACCOUNT_RESEARCHER,
                name="Account Researcher",
                description="Enriches company firmographics, locations, and tech stack usage.",
                input_types=["company_name", "domain"],
                output_types=["enriched_company_profile"],
            ),
            GtmAgentContract(
                role=AgentRole.BUYER_MAPPER,
                name="Buyer Mapper",
                description="Identifies the primary decision maker (Owner, Founder, MD, Partner).",
                input_types=["company_profile"],
                output_types=["decision_maker_contact"],
            ),
            GtmAgentContract(
                role=AgentRole.PAIN_MINER,
                name="Pain Miner",
                description="Extracts precise, quantifiable operational bottlenecks and cost leakages.",
                input_types=["transcripts", "job_posts", "complaints"],
                output_types=["quantified_pain_point"],
            ),
            GtmAgentContract(
                role=AgentRole.AI_FIT_ARCHITECT,
                name="AI Fit Architect",
                description="Selects the optimal assistant SKU from the 15-product AI Assistant Catalog.",
                input_types=["pain_point", "industry"],
                output_types=["recommended_assistant_sku", "scope_of_work"],
            ),
            GtmAgentContract(
                role=AgentRole.ROI_AGENT,
                name="ROI Calculator",
                description="Calculates expected monthly ROI, cost savings, and revenue reactivation.",
                input_types=["pain_point", "industry_metrics"],
                output_types=["roi_projection_usd"],
            ),
            GtmAgentContract(
                role=AgentRole.QUALIFIER,
                name="Lead Qualifier",
                description="Applies strict 100-point intent formula and eliminates zero-intent leads.",
                input_types=["candidate_card"],
                output_types=["intent_score", "intent_tier"],
            ),
            GtmAgentContract(
                role=AgentRole.PERSONALIZER,
                name="Outreach Personalizer",
                description="Generates personalized 1-sentence phone hooks and 3-sentence cold emails.",
                input_types=["buyer_profile", "pain_point", "assistant_sku"],
                output_types=["phone_hook", "cold_email", "linkedin_dm"],
            ),
            GtmAgentContract(
                role=AgentRole.CHANNEL_ROUTER,
                name="Channel Router",
                description="Selects optimal communication rail (Phone, SMS, Email, LinkedIn).",
                input_types=["contact_channels", "urgency"],
                output_types=["primary_channel", "fallback_channel"],
            ),
            GtmAgentContract(
                role=AgentRole.VOICE_AGENT,
                name="Voice Dialer Agent",
                description="Powers real-time live phone dialing and automated conversation bridges.",
                input_types=["phone_number", "opening_hook"],
                output_types=["call_transcript", "disposition"],
            ),
            GtmAgentContract(
                role=AgentRole.CONVERSATION_AGENT,
                name="Conversation Agent",
                description="Handles live multi-turn chat and SMS exchanges with leads.",
                input_types=["incoming_message", "conversation_history"],
                output_types=["response_message", "suggested_action"],
            ),
            GtmAgentContract(
                role=AgentRole.IDENTITY_AGENT,
                name="Identity Agent",
                description="Verifies whether the responder is the true owner or authorized decision maker.",
                input_types=["caller_info", "county_records"],
                output_types=["identity_state", "is_authorized"],
            ),
            GtmAgentContract(
                role=AgentRole.MEETING_AGENT,
                name="Meeting Booker",
                description="Negotiates calendar time slots and generates Google Meet confirmation invites.",
                input_types=["availability", "lead_email"],
                output_types=["meeting_calendar_event"],
            ),
            GtmAgentContract(
                role=AgentRole.FOLLOWUP_AGENT,
                name="Follow-Up Agent",
                description="Schedules automated nurturing and follow-up touches for non-responsive leads.",
                input_types=["last_touch_date", "lead_state"],
                output_types=["next_touch_datetime", "nurture_copy"],
            ),
            GtmAgentContract(
                role=AgentRole.OBJECTION_AGENT,
                name="Objection Handler",
                description="Provides real-time rebuttal scripts for common AI sales objections.",
                input_types=["objection_text"],
                output_types=["rebuttal_script", "proof_point"],
            ),
            GtmAgentContract(
                role=AgentRole.DEAL_STRATEGIST,
                name="Deal Strategist",
                description="Formulates closing strategies, custom retainer packages, and discount boundaries.",
                input_types=["deal_stage", "budget_range"],
                output_types=["negotiation_terms", "closing_playbook"],
            ),
            GtmAgentContract(
                role=AgentRole.REVOPS_AGENT,
                name="RevOps Engine",
                description="Maintains pipeline hygiene, CRM synchronization, and conversion metrics.",
                input_types=["deal_events"],
                output_types=["pipeline_health", "velocity_report"],
            ),
            GtmAgentContract(
                role=AgentRole.ATTRIBUTION_AGENT,
                name="Attribution Engine",
                description="Tracks multi-touch progression from source signal to Neteller cash received.",
                input_types=["deal_journey"],
                output_types=["attribution_graph", "roi_by_source"],
            ),
            GtmAgentContract(
                role=AgentRole.EXPERIMENT_AGENT,
                name="A/B Experimenter",
                description="Executes controlled A/B test variations on hooks, pricing, and timing.",
                input_types=["campaign_variations"],
                output_types=["winner_variant", "statistical_significance"],
            ),
            GtmAgentContract(
                role=AgentRole.LEARNING_AGENT,
                name="Learning Engine",
                description="Aggregates conversion feedback to refine vertical scoring weights.",
                input_types=["deal_outcomes"],
                output_types=["feedback_for_scoring", "weight_adjustments"],
            ),
            GtmAgentContract(
                role=AgentRole.GTM_COMMANDER,
                name="GTM Master Commander",
                description="Orchestrates full GTM pipeline, ranks actions, and delegates tasks safely.",
                input_types=["gtm_state"],
                output_types=["next_best_actions", "delegations"],
            ),
            # --- Expanded scope agents ---
            GtmAgentContract(
                role=AgentRole.EMAIL_DISPATCHER,
                name="Gmail Outbound Agent",
                description="Sends production cold emails, follow-ups, and proposals via the Gmail pool with Production Gate enforcement.",
                input_types=["entity_id", "to_email", "subject", "body"],
                output_types=["send_result", "dispatch_log"],
            ),
            GtmAgentContract(
                role=AgentRole.FACEBOOK_INTEL,
                name="Facebook Intelligence Agent",
                description="Harvests Facebook Groups, Pages, and marketplace posts for B2B pain signals, buyer contacts, and competitor intelligence.",
                input_types=["keywords", "group_ids", "page_queries"],
                output_types=["groups", "pages", "intent_signals", "enriched_prospects"],
            ),
            GtmAgentContract(
                role=AgentRole.NEWS_MONITOR,
                name="Google News Monitor",
                description="Scans Google News RSS for industry pain signals, funding events, hiring surges, and technology adoption trends.",
                input_types=["verticals", "company_names"],
                output_types=["news_signals", "vertical_trends"],
            ),
        ]

        for contract in contracts:
            self._agents[contract.role] = contract

    def get_agent(self, role: AgentRole) -> Optional[GtmAgentContract]:
        """Retrieve a specific agent contract by role."""
        return self._agents.get(role)

    def register_handler(self, role: AgentRole, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register or override an active handler for a specific agent role."""
        if role in self._agents:
            self._agents[role].handler = handler

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all 26 registered GTM agent contracts."""
        return [c.to_dict() for c in self._agents.values()]
