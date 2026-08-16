"""
GTM COMMANDER
=============================================================================
Primary Master Orchestrator for the MBM Go-To-Market Ecosystem.

Deterministic Loop:
  read GTM state -> identify opportunities -> rank next actions ->
  delegate safely -> record event -> update state

Strict Safety Rule:
  DRY RUN ONLY by default. Never places unsolicited calls or modifies live
  production dialer / CRM records without explicit approval.
=============================================================================
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine
from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
from MBM.LeadEngine.gtm.evidence import GtmEvidence, EvidenceStore
from MBM.LeadEngine.gtm.action_ranker import ActionRanker, NextBestAction, ChannelType, ActionType
from MBM.LeadEngine.gtm.agent_registry import AgentRegistry, AgentRole
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

ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


class GtmCommander:
    """
    Master Go-To-Market Commander.
    Coordinates all GTM adapters, state machines, action rankers, and event bus.
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.event_bus = GtmEventBus()
        self.agent_registry = AgentRegistry()
        self.evidence_store = EvidenceStore()
        self.attribution_tracker = AttributionTracker()
        self.learning_engine = GtmLearningEngine()
        self.action_ranker = ActionRanker()

        # Adapters
        self.buyer_hunter_adapter = BuyerHunterAdapter()
        self.canonical_adapter = CanonicalMemoryAdapter()
        self.dialer_adapter = DialerAdapter()
        self.identity_adapter = IdentityAdapter()
        self.crm_adapter = CRMAdapter()
        self.verification_adapter = VerificationAdapter()

        # State tracking
        self._state_machines: Dict[str, GtmStateMachine] = {}

    # -------------------------------------------------------------------------
    # 1. READ GTM STATE
    # -------------------------------------------------------------------------
    def read_gtm_state(self) -> Dict[str, Any]:
        """Aggregate current state across all connected MBM systems."""
        hot_buyers = self.buyer_hunter_adapter.get_hot_buyers()
        all_prospects = self.buyer_hunter_adapter.get_all_prospects()
        canonical_deals = self.canonical_adapter.get_deals()
        callable_leads = self.dialer_adapter.get_callable_leads()

        return {
            "hot_buyers_count": len(hot_buyers),
            "total_prospects_count": len(all_prospects),
            "canonical_deals_count": len(canonical_deals),
            "callable_dialer_leads_count": len(callable_leads),
            "hot_buyers": hot_buyers,
            "all_prospects": all_prospects,
            "canonical_deals": canonical_deals,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # 2. IDENTIFY OPPORTUNITIES
    # -------------------------------------------------------------------------
    def identify_opportunities(self) -> List[Dict[str, Any]]:
        """Extract and normalize candidate opportunities for action ranking."""
        raw_prospects = self.buyer_hunter_adapter.get_all_prospects()
        if not raw_prospects:
            raw_prospects = self.buyer_hunter_adapter.get_hot_buyers()

        normalized_opps = []
        for p in raw_prospects:
            entity_id = p.get("id") or p.get("company", "UNKNOWN")
            
            # Initialize state machine if not already tracked
            if entity_id not in self._state_machines:
                initial_state = GtmState.QUALIFIED if p.get("tier") in {"HOT", "HIGH INTENT"} else GtmState.DISCOVERED
                self._state_machines[entity_id] = GtmStateMachine(initial_state, entity_id=entity_id)

            identity_state = self.identity_adapter.get_identity_state(entity_id)
            is_suppressed = self.dialer_adapter.is_suppressed(p.get("phone", ""))

            ai_fit_raw = p.get("recommended_assistant_sku") or p.get("recommended_ai_assistant") or "AI-ASSISTANT-VIP-RETAINER"
            if isinstance(ai_fit_raw, dict):
                ai_fit_str = ai_fit_raw.get("assistant_name") or ai_fit_raw.get("sku") or "AI Assistant Automation"
            else:
                ai_fit_str = str(ai_fit_raw)

            opp = {
                "id": entity_id,
                "company": p.get("company", "Target Enterprise"),
                "decision_maker": p.get("decision_maker") or p.get("role") or "Authorized Executive",
                "role": p.get("role", "Owner / Decision Maker"),
                "industry": p.get("industry", "B2B Services"),
                "phone": p.get("phone", ""),
                "email": p.get("email", ""),
                "pain_point": p.get("pain_point") or p.get("pain_description") or "Operations bottleneck",
                "intent_signal": p.get("intent_signal", "Automated workflow request"),
                "intent_score": p.get("intent_score", 85.0),
                "tier": p.get("tier", "HIGH INTENT"),
                "why_this_company": p.get("why_this_company") or f"High pain and verified authority at {p.get('company')}.",
                "why_now": p.get("why_now", "Active hiring urgency"),
                "recommended_assistant_sku": ai_fit_str,
                "expected_revenue": p.get("monthly_retainer_fee") or p.get("expected_revenue", 2000.0),
                "confidence": p.get("confidence") or (p.get("confidence_score", 85.0) / 100.0),
                "identity_state": identity_state,
                "is_suppressed": is_suppressed,
                "state": self._state_machines[entity_id].current_state.value,
                "source": p.get("source", "SignalHarvester"),
            }

            # Record evidence in evidence store
            if p.get("source"):
                try:
                    evidence = GtmEvidence(
                        claim=opp["why_this_company"],
                        source=p.get("source", "Harvester"),
                        source_reference=p.get("post_content") or p.get("source", "Verified Feed"),
                        confidence=opp["confidence"],
                        agent="INTENT_HUNTER",
                    )
                    self.evidence_store.add_evidence(entity_id, evidence)
                except Exception:
                    pass

            normalized_opps.append(opp)

        return normalized_opps

    # -------------------------------------------------------------------------
    # 3. RANK NEXT ACTIONS
    # -------------------------------------------------------------------------
    def rank_next_actions(self, limit: int = 10) -> List[NextBestAction]:
        """Rank opportunities using mathematical priority formula."""
        opps = self.identify_opportunities()
        return self.action_ranker.rank_opportunities(opps, limit=limit)

    # -------------------------------------------------------------------------
    # 4. DELEGATE SAFELY
    # -------------------------------------------------------------------------
    def delegate_safely(self, action: NextBestAction) -> Dict[str, Any]:
        """
        Delegate an action to the appropriate agent contract.
        In dry-run mode, generates execution payload without triggering real side-effects.
        """
        target_role = AgentRole.VOICE_AGENT if action.recommended_channel == ChannelType.PHONE else AgentRole.PERSONALIZER
        agent_contract = self.agent_registry.get_agent(target_role)

        payload = {
            "entity_id": action.entity_id,
            "company": action.company,
            "buyer": action.buyer,
            "channel": action.recommended_channel.value,
            "action_type": action.action_type.value,
            "ai_fit": action.ai_fit,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            result = {
                "delegated_to": target_role.value,
                "status": "DRY_RUN_QUEUED",
                "payload": payload,
            }
        else:
            result = agent_contract.execute(payload) if agent_contract else {"status": "NO_AGENT"}

        # Record event
        self.record_event(
            event_type=GtmEventType.OUTREACH_READY,
            entity_id=action.entity_id,
            payload={"action": action.to_dict(), "result": result},
        )
        return result

    # -------------------------------------------------------------------------
    # 5. RECORD EVENT
    # -------------------------------------------------------------------------
    def record_event(
        self,
        event_type: GtmEventType,
        entity_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> GtmEvent:
        """Publish a typed event to the GTM Event Bus."""
        event = GtmEvent(
            event_type=event_type,
            entity_id=entity_id,
            producer="GTM_COMMANDER",
            payload=payload or {},
        )
        self.event_bus.publish(event)
        return event

    # -------------------------------------------------------------------------
    # 6. UPDATE STATE
    # -------------------------------------------------------------------------
    def update_state(self, entity_id: str, target_state: GtmState, reason: str = "") -> GtmState:
        """Update opportunity lifecycle state with validation."""
        if entity_id not in self._state_machines:
            self._state_machines[entity_id] = GtmStateMachine(GtmState.DISCOVERED, entity_id=entity_id)
        
        sm = self._state_machines[entity_id]
        new_state = sm.transition(target_state, reason=reason, actor="GTM_COMMANDER")
        
        self.record_event(
            event_type=GtmEventType.OUTREACH_READY if new_state == GtmState.QUALIFIED else GtmEventType.NEW_BUYER,
            entity_id=entity_id,
            payload={"new_state": new_state.value, "reason": reason},
        )
        return new_state

    # -------------------------------------------------------------------------
    # 7. EXECUTE DRY-RUN
    # -------------------------------------------------------------------------
    def execute_dry_run(self, limit: int = 10) -> str:
        """Run full commander discovery and output ranked next actions in exact required format."""
        ranked_actions = self.rank_next_actions(limit=limit)
        
        output_lines = ["TOP NEXT ACTIONS", ""]
        for idx, action in enumerate(ranked_actions, start=1):
            output_lines.append(action.format_dry_run(index=idx))

        formatted_output = "\n".join(output_lines)
        return formatted_output


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Commander")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Execute in deterministic dry-run mode")
    parser.add_argument("--limit", type=int, default=10, help="Number of next actions to output")
    args = parser.parse_args()

    commander = GtmCommander(dry_run=args.dry_run)
    result = commander.execute_dry_run(limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()
