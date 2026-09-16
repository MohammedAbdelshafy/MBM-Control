"""GTM end-to-end: signal -> draft -> gate -> CRM proposal -> audit (Part 13).

Every stage uses real deterministic modules. Evidence survives each stage.
Unsupported claims are rejected, suppression respected, sends stay gated.
No external sends, writes, or network calls.
"""

import tempfile
import unittest
from pathlib import Path

from MBM.ContecRadar.slice_a import run_slice_a
from MBM.DemandFactory.models import Opportunity
from MBM.DemandFactory.monetization import build_monetization_plan
from MBM.DemandFactory.router import choose_revenue_route
from MBM.LeadEngine.gtm import guarded_actions as GA
from MBM.LeadEngine.gtm.evidence import EvidenceStore, GtmEvidence
from MBM.LeadEngine.gtm.factory_bridge import get_binding, pipeline_state
from MBM.LeadEngine.gtm.production_gate import ProductionGate
from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine
from jarvis_control_plane.factory_routing import build_evidence, route_capability


class GtmEndToEndTests(unittest.TestCase):
    def test_signal_to_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = ProductionGate(approvals_file=Path(tmp) / "approvals.json")

            # MARKET SIGNAL -> RESEARCH (real offline discovery).
            radar = run_slice_a([{
                "signal_id": "gtm-e2e-1",
                "title": "Contractors lose bids to slow estimating",
                "body": "Small contractors report estimating backlogs verified in forum threads",
                "source": "offline_fixture"}])
            self.assertGreaterEqual(len(radar.opportunities), 1)

            # EVIDENCE / ENRICHMENT (real evidence store; fixture labeled).
            store = EvidenceStore()
            store.add_evidence("acc-e2e", GtmEvidence(
                claim="Acme Contracting reports estimating backlogs",
                source="offline_fixture", source_reference="gtm-e2e-1",
                confidence=0.7, agent="test"))
            self.assertGreaterEqual(store.calculate_entity_confidence("acc-e2e"), 0.0)
            evidence_ids = [e.evidence_id for e in store.get_evidence_for_entity("acc-e2e")]
            self.assertTrue(evidence_ids)

            # QUALIFICATION + SCORING (real gates).
            prospect = {"company": "Acme Contracting", "contact_name": "Sam",
                        "phone": "+15551234567", "email": "sam@acmecontracting.example",
                        "pain_point": "estimating backlogs",
                        "why_this_company": "matches contractor ICP",
                        "confidence": 0.8, "recommended_channel": "EMAIL"}
            verdict = gate.evaluate_gate(prospect)
            self.assertTrue(verdict["evidence_valid"])
            self.assertTrue(verdict["contactable"])
            self.assertFalse(verdict["can_execute"])  # no human approval yet
            self.assertEqual(verdict["approval_status"], "PENDING_APPROVAL")

            score = GA.score_account({"icp_fit": 0.9, "problem_signal": 0.8,
                                      "evidence_quality": 0.7, "contactability": 0.8,
                                      "timing_signal": 0.6})
            self.assertEqual(score.tier, "QUALIFIED")

            # Dedupe keeps the single prospect.
            deduped = GA.dedupe_prospects([dict(prospect, domain="acmecontracting.example")])
            self.assertEqual(deduped["kept_count"], 1)

            # OFFER MATCH (real router) + MESSAGE DRAFT (evidence-only).
            opportunity = Opportunity(
                opportunity_id="opp-gtm-e2e", problem="estimating backlogs",
                buyer_segment="contractors", distributor_type="direct",
                price_potential=499,
                metadata={"launch_price": 499,
                          "buyer_outcome": "produce first estimates faster",
                          "proof_assets": ["takeoff workflow demo"],
                          "delivery_assets": ["lead-cleaner-style report"],
                          "checkout_rails": [], "acquisition_channels": ["direct"]})
            plan = build_monetization_plan(opportunity, product_name="Estimating Sprint")
            route = choose_revenue_route(opportunity, plan)
            self.assertTrue(route.rail)

            draft = GA.draft_outreach(
                prospect={"company": "Acme Contracting", "contact_name": "Sam"},
                problem="estimating backlogs",
                proof="demo of the verified takeoff workflow",
                evidence_ids=evidence_ids)
            self.assertEqual(draft.status, "draft_pending_review")

            # Unsupported claim rejected mid-pipeline.
            with self.assertRaises(ValueError):
                GA.draft_outreach(
                    prospect={"company": "Acme"}, problem="backlogs",
                    proof="guaranteed 5x ROI", evidence_ids=evidence_ids)

            # APPROVAL GATE: send capability never routes without approval.
            with self.assertRaises(PermissionError):
                route_capability("outreach_send", "PACKAGE",
                                 approval={"approved": True, "approver": "human"})
            self.assertEqual(get_binding("outreach_send").status, "BLOCKED")

            # RESPONSE: opt-out routes to suppression.
            inbound = GA.response_classifier("Please stop emailing me")
            self.assertEqual(inbound["label"], "UNSUBSCRIBE")

            # CRM: proposal only, never a write.
            overlay = GA.crm_overlay_proposal(
                entity_id="acc-e2e", stage=pipeline_state("CRM"),
                evidence_ids=evidence_ids, activity="log discovery call")
            self.assertFalse(overlay["executed"])

            # PIPELINE: validated walk + illegal move rejected.
            machine = GtmStateMachine(entity_id="acc-e2e")
            for target in (GtmState.QUALIFYING, GtmState.QUALIFIED):
                machine.transition(target, reason="e2e", actor="test")
            self.assertEqual(machine.current_state, GtmState.QUALIFIED)
            with self.assertRaises(Exception):
                machine.transition(GtmState.WON, reason="skip", actor="test")

            # AUDIT: structured evidence closes the loop.
            spec, decision = route_capability("lead_qualification", "SCORE")
            audit = build_evidence(
                spec=spec, actor="gtm-e2e", inputs={"entity_id": "acc-e2e"},
                outputs={"tier": score.tier, "gate": verdict["can_execute"]},
                approval=None, policy_decision=decision, success=True,
                state="MEASURED")
            self.assertEqual(audit.state, "MEASURED")
            self.assertTrue(audit.success)


if __name__ == "__main__":
    unittest.main()
