"""
MBM GTM (Go-To-Market) Architecture Package
=============================================================================
Parallel-safe GTM orchestration layer, event bus, state machine, evidence,
attribution, action ranking, agent registry, and learning feedback.
"""

from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine, InvalidStateTransitionError
from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
from MBM.LeadEngine.gtm.evidence import GtmEvidence, EvidenceStore
from MBM.LeadEngine.gtm.action_ranker import ActionRanker, NextBestAction, ActionType, ChannelType, ChannelRouter
from MBM.LeadEngine.gtm.agent_registry import AgentRegistry, GtmAgentContract, AgentRole
from MBM.LeadEngine.gtm.attribution import AttributionTracker, Touchpoint, RevenueStage
from MBM.LeadEngine.gtm.learning import GtmLearningEngine, OutcomeType
from MBM.LeadEngine.gtm.adapters import (
    BuyerHunterAdapter,
    CanonicalMemoryAdapter,
    DialerAdapter,
    IdentityAdapter,
    CRMAdapter,
    VerificationAdapter,
)

__all__ = [
    "GtmState",
    "GtmStateMachine",
    "InvalidStateTransitionError",
    "GtmEvent",
    "GtmEventType",
    "GtmEventBus",
    "GtmEvidence",
    "EvidenceStore",
    "ActionRanker",
    "NextBestAction",
    "ActionType",
    "ChannelType",
    "ChannelRouter",
    "AgentRegistry",
    "GtmAgentContract",
    "AgentRole",
    "AttributionTracker",
    "Touchpoint",
    "RevenueStage",
    "GtmLearningEngine",
    "OutcomeType",
    "BuyerHunterAdapter",
    "CanonicalMemoryAdapter",
    "DialerAdapter",
    "IdentityAdapter",
    "CRMAdapter",
    "VerificationAdapter",
]
