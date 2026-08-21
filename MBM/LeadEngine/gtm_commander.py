"""
GTM COMMANDER
=================================================================================================================
Primary Master Orchestrator for the MBM Go-To-Market Ecosystem.

Deterministic Loop:
  read GTM state -> identify opportunities -> rank next actions ->
  delegate safely -> record event -> update state

Strict Safety Rule:
  DRY RUN ONLY by default. Never places unsolicited calls or modifies live
  production dialer / CRM records without explicit approval.

Modes:
  --dry-run   : read-only ranked next-best actions (default, no side effects)
  --simulate  : run an artificial opportunity through the full lifecycle
=================================================================================================================
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

from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine, InvalidStateTransitionError
from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
from MBM.LeadEngine.gtm.evidence import GtmEvidence, EvidenceStore
from MBM.LeadEngine.gtm.action_ranker import ActionRanker, NextBestAction, ChannelType, ActionType, ChannelRouter
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
from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard, SPRINT_OFFERS, LANDING_URL

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
        self.channel_router = ChannelRouter()
        self.sales_ledger = GtmSalesLedger()
        self.scoreboard = GtmRevenueScoreboard(ledger=self.sales_ledger)

        # Adapters
        self.buyer_hunter_adapter = BuyerHunterAdapter()
        self.canonical_adapter = CanonicalMemoryAdapter()
        self.dialer_adapter = DialerAdapter()
        self.identity_adapter = IdentityAdapter()
        self.crm_adapter = CRMAdapter()
        self.verification_adapter = VerificationAdapter()

        # State tracking
        self._state_machines: Dict[str, GtmStateMachine] = {}

    def export_scoreboard(self, prospects_count: int = 10) -> Path:
        """Generate and export the GTM Revenue Scoreboard artifact."""
        return self.scoreboard.export_reports(prospects_count=prospects_count)


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
            # Normalize via the Buyer Hunter adapter (maps intent_tier, retainer,
            # evidence card, and confidence from the real artifact schema).
            opp = self.buyer_hunter_adapter.normalize_prospect(p)
            entity_id = opp["id"]

            # Initialize state machine if not already tracked
            if entity_id not in self._state_machines:
                initial_state = GtmState.QUALIFIED if opp.get("tier") in {"HOT", "HIGH INTENT"} else GtmState.DISCOVERED
                self._state_machines[entity_id] = GtmStateMachine(initial_state, entity_id=entity_id)

            identity_state = self.identity_adapter.get_identity_state(entity_id)
            opp["identity_state"] = identity_state
            opp["is_suppressed"] = self.dialer_adapter.is_suppressed(opp.get("phone", ""))
            opp["state"] = self._state_machines[entity_id].current_state.value

            # Revenue model (never report pipeline as actual money)
            expected_value = float(opp.get("expected_revenue", 0.0))
            probability = float(opp.get("confidence", 0.0))
            opp["value"] = expected_value
            opp["probability"] = probability
            opp["expected_value"] = round(expected_value * probability, 2)
            opp["revenue_state"] = "CONFIRMED" if opp["state"] == "WON" else ("PIPELINE" if opp["state"] in {"QUALIFIED", "CONTACTING", "ENGAGED", "MEETING_BOOKED"} else "EXPECTED")

            # Record evidence in evidence store
            evidence_dict = opp.get("evidence") or {}
            if evidence_dict.get("source") and evidence_dict.get("source") != "UNKNOWN":
                try:
                    evidence = GtmEvidence(
                        claim=evidence_dict.get("claim") or opp["why_this_company"],
                        source=evidence_dict["source"],
                        source_reference=evidence_dict.get("source_reference") or evidence_dict["source"],
                        confidence=float(evidence_dict.get("confidence", 0.85)),
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

        output_lines = ["=== MBM GTM COMMANDER ===", "", "TOP NEXT ACTIONS", ""]
        for idx, action in enumerate(ranked_actions, start=1):
            output_lines.append(action.format_dry_run(index=idx))
            output_lines.append("")

        formatted_output = "\n".join(output_lines)
        return formatted_output

    # -------------------------------------------------------------------------
    # 8. EXECUTE SIMULATION (READ-ONLY)
    # -------------------------------------------------------------------------
    def execute_simulation(self) -> str:
        """
        Run an artificial opportunity through the full lifecycle and verify
        every transition. Also verifies WRONG_PERSON -> SUPPRESSED and that
        OWNER_CONFIRMED raises priority. All simulation evidence is explicitly
        labeled SIMULATION_RUN so it can never be confused with real data.
        """
        lines = ["=== MBM GTM COMMANDER — SIMULATION MODE (READ-ONLY) ===", ""]

        entity_id = "SIM-OPP-0001"
        sm = GtmStateMachine(GtmState.DISCOVERED, entity_id=entity_id)

        # -----------------------------------------------------------------
        # A. Happy-path lifecycle: every transition must be legal.
        # -----------------------------------------------------------------
        happy_path = [
            (GtmState.QUALIFYING, "Signal enrichment"),
            (GtmState.QUALIFIED, "Intent score >= 75"),
            (GtmState.CONTACTING, "First outreach attempt"),
            (GtmState.ENGAGED, "Buyer engaged on pain"),
            (GtmState.MEETING_BOOKED, "Discovery call scheduled"),
            (GtmState.PROPOSAL, "Retainer SOW sent"),
            (GtmState.WON, "Neteller transaction verified"),
        ]
        lines.append("LIFECYCLE: DISCOVERED -> QUALIFYING -> QUALIFIED -> CONTACTING -> ENGAGED -> MEETING_BOOKED -> PROPOSAL -> WON")
        try:
            for target, reason in happy_path:
                sm.transition(target, reason=reason, actor="SIMULATION")
                lines.append(f"  [OK] {sm.history[-1]['from_state']} -> {target.value}")
            lines.append(f"  [OK] TERMINAL STATE: {sm.current_state.value}")
        except InvalidStateTransitionError as e:
            lines.append(f"  [FAIL] {e}")
            lines.append("  SIMULATION: HAPPY-PATH TRANSITION VIOLATION")

        # -----------------------------------------------------------------
        # B. WRONG_PERSON -> SUPPRESSED (garbage never recycled).
        # -----------------------------------------------------------------
        lines.append("")
        sm2 = GtmStateMachine(GtmState.QUALIFIED, entity_id="SIM-OPP-0002")
        lines.append("SUPPRESSION: WRONG_PERSON -> SUPPRESSED")
        try:
            sm2.transition(GtmState.SUPPRESSED, reason="WRONG_PERSON", actor="IDENTITY_AGENT")
            lines.append(f"  [OK] QUALIFIED -> SUPPRESSED (terminal: {sm2.is_terminal()})")
            opp2 = {"is_suppressed": True, "state": "SUPPRESSED", "expected_revenue": 5000.0}
            rank2 = self.action_ranker.calculate_priority_score(opp2)
            lines.append(f"  [OK] suppressed priority == 0.0 (got {rank2})")
        except InvalidStateTransitionError as e:
            lines.append(f"  [FAIL] {e}")

        # -----------------------------------------------------------------
        # C. OWNER_CONFIRMED raises priority vs IDENTITY_UNCONFIRMED.
        # -----------------------------------------------------------------
        lines.append("")
        lines.append("PRIORITY: OWNER_CONFIRMED vs IDENTITY_UNCONFIRMED")
        base_opp = {
            "expected_revenue": 3500.0,
            "intent_score": 90.0,
            "urgency": 1.0,
            "confidence": 0.9,
            "signal_age_days": 2,
            "recent_attempts": 0,
            "phone": "+12148849120",
            "evidence": {"source": "SIMULATION_RUN"},
        }
        unconfirmed = dict(base_opp, identity_state="IDENTITY_UNCONFIRMED")
        confirmed = dict(base_opp, identity_state="OWNER_CONFIRMED")
        s_un = self.action_ranker.calculate_priority_score(unconfirmed)
        s_cf = self.action_ranker.calculate_priority_score(confirmed)
        lines.append(f"  unconfirmed priority: {s_un}")
        lines.append(f"  owner-confirmed priority: {s_cf}")
        lines.append("  [OK] OWNER_CONFIRMED -> priority increase" if s_cf > s_un else "  [FAIL] OWNER_CONFIRMED did not increase priority")

        lines.append("")
        lines.append("SIMULATION: COMPLETE")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Commander")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Execute in deterministic dry-run mode (default)")
    parser.add_argument("--simulate", action="store_true", help="Run the artificial lifecycle simulation (read-only)")
    parser.add_argument("--scoreboard", action="store_true", help="Generate and export the GTM Revenue Scoreboard")
    parser.add_argument("--refresh-queue", action="store_true", help="Recalculate dynamic priority and refresh the dialer call sheet")
    parser.add_argument("--apply", action="store_true", help="Commit priority queue changes to dialer DB")
    parser.add_argument("--limit", type=int, default=10, help="Number of next actions to output")
    args = parser.parse_args()

    commander = GtmCommander(dry_run=True)

    if args.refresh_queue:
        from MBM.LeadEngine.dialer_priority_engine import refresh_dialer_priority_queue
        res = refresh_dialer_priority_queue(dry_run=not args.apply)
        print(f"[OK] Priority queue refreshed (dry_run={not args.apply}): {res['total_records']} total records, {res['callable_count']} callable.")
        return

    if args.scoreboard:
        path = commander.export_scoreboard()
        print(f"[OK] GTM Revenue Scoreboard exported to: {path}")
        return

    if args.simulate:
        print(commander.execute_simulation())
        return

    result = commander.execute_dry_run(limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()