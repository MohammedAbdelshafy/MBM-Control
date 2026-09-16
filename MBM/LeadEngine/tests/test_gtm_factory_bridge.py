"""Tests for GTM factory bridge + guarded actions (Part 12 core)."""

import json
import tempfile
import unittest
from pathlib import Path

from MBM.LeadEngine.gtm import guarded_actions as GA
from MBM.LeadEngine.gtm.factory_bridge import (
    blocked_roles,
    get_binding,
    list_bindings,
    pipeline_state,
    retired_agents,
    wired_roles,
)
from jarvis_control_plane.factory_routing import route_capability, stage_capabilities


class BridgeMapTests(unittest.TestCase):
    def test_sixteen_roles_mapped(self):
        self.assertEqual(len(list_bindings()), 16)

    def test_unknown_role_denied(self):
        with self.assertRaises(KeyError):
            get_binding("growth_hacker")

    def test_every_binding_has_reason_and_permission(self):
        for binding in list_bindings():
            self.assertTrue(binding.reason, binding.role)
            self.assertIn(binding.permission, (
                "READ_ONLY", "SAFE_WRITE", "CONTROLLED_WRITE",
                "CONSEQUENTIAL_EXTERNAL_ACTION"))

    def test_wired_bindings_reference_real_modules(self):
        for binding in list_bindings():
            if binding.status == "WIRED":
                self.assertTrue(binding.wired_via, binding.role)
                for ref in binding.wired_via:
                    self.assertNotIn("PROCESSED_STUB", ref)

    def test_outreach_send_blocked(self):
        binding = get_binding("outreach_send")
        self.assertEqual(binding.status, "BLOCKED")
        self.assertTrue(binding.approval_required)
        self.assertIn("outreach_send", blocked_roles())

    def test_roi_agent_retired(self):
        retired = retired_agents()
        self.assertIn("ROI_AGENT", retired)
        self.assertIn("evidence-first", retired["ROI_AGENT"])

    def test_pipeline_mapping_and_unknown_denied(self):
        self.assertEqual(pipeline_state("MESSAGE_DRAFT"), "QUALIFIED")
        self.assertEqual(pipeline_state("OUTREACH"), "CONTACTING")
        self.assertEqual(pipeline_state("LEARN"), "NURTURE")
        with self.assertRaises(KeyError):
            pipeline_state("MOONSHOT")

    def test_wired_and_blocked_sets(self):
        self.assertIn("lead_cleaning", wired_roles())
        self.assertIn("lead_qualification", wired_roles())
        self.assertNotIn("outreach_send", wired_roles())


class ClassifierTests(unittest.TestCase):
    def test_unsubscribe_precedence(self):
        result = GA.response_classifier("Yes I'm interested, but please stop emailing me")
        self.assertEqual(result["label"], "UNSUBSCRIBE")
        self.assertEqual(result["required_action"], "suppress_immediately")

    def test_disinterest_before_interest(self):
        self.assertEqual(GA.response_classifier("Not interested, thanks")["label"], "NOT_A_FIT")

    def test_interested(self):
        result = GA.response_classifier("This looks great, let's book a call")
        self.assertEqual(result["label"], "INTERESTED")

    def test_question(self):
        result = GA.response_classifier("How does onboarding work?")
        self.assertEqual(result["label"], "QUESTION")

    def test_objection(self):
        result = GA.response_classifier("We are worried about the contract terms")
        self.assertEqual(result["label"], "OBJECTION")

    def test_not_now(self):
        self.assertEqual(GA.response_classifier("Busy now, revisit next quarter")["label"], "NOT_NOW")

    def test_unknown_and_malformed(self):
        self.assertEqual(GA.response_classifier("ok")["label"], "UNKNOWN")
        self.assertEqual(GA.response_classifier("")["label"], "UNKNOWN")
        self.assertEqual(GA.response_classifier(None)["label"], "UNKNOWN")
        self.assertEqual(GA.response_classifier(123)["label"], "UNKNOWN")

    def test_determinism(self):
        text = "What does implementation cost?"
        self.assertEqual(GA.response_classifier(text), GA.response_classifier(text))


class ScoringTests(unittest.TestCase):
    def test_perfect_signals_qualified(self):
        result = GA.score_account({k: 1.0 for k in
                                   ("icp_fit", "problem_signal", "evidence_quality",
                                    "contactability", "timing_signal")})
        self.assertEqual(result.tier, "QUALIFIED")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.reasons, [])

    def test_empty_signals_disqualified(self):
        result = GA.score_account({})
        self.assertEqual(result.tier, "DISQUALIFIED")
        self.assertEqual(result.score, 0.0)

    def test_missing_factors_score_zero(self):
        result = GA.score_account({"icp_fit": 1.0})
        self.assertEqual(result.tier, "DISQUALIFIED")

    def test_malformed_signals(self):
        result = GA.score_account("high intent")
        self.assertEqual(result.tier, "DISQUALIFIED")
        self.assertIn("malformed_signals_not_a_dict", result.reasons)

    def test_explained_factors(self):
        result = GA.score_account({"icp_fit": 0.9, "problem_signal": 0.8,
                                   "evidence_quality": 0.9, "contactability": 0.9,
                                   "timing_signal": 0.9})
        self.assertEqual(result.tier, "QUALIFIED")
        self.assertIn("icp_fit", result.factors)


class DraftingTests(unittest.TestCase):
    def _prospect(self, **overrides):
        base = {"company": "Acme Contracting", "contact_name": "Sam",
                "sender_name": "MBM"}
        base.update(overrides)
        return base

    def test_valid_draft(self):
        draft = GA.draft_outreach(
            prospect=self._prospect(), problem="estimating backlogs",
            proof="demo of the verified takeoff workflow",
            evidence_ids=["sig-1"])
        self.assertEqual(draft.status, "draft_pending_review")
        self.assertIn("Acme Contracting", draft.body)
        self.assertEqual(draft.evidence_ids, ["sig-1"])

    def test_banned_claims_rejected(self):
        for bad_proof in ("clients see 10x ROI in a month",
                          "includes testimonials from happy buyers",
                          "risk-free guarantee, #1 rated"):
            with self.subTest(bad=bad_proof):
                with self.assertRaises(ValueError):
                    GA.draft_outreach(prospect=self._prospect(),
                                      problem="estimating backlogs",
                                      proof=bad_proof, evidence_ids=["sig-1"])

    def test_injection_via_fields_rejected(self):
        with self.assertRaises(ValueError):
            GA.draft_outreach(
                prospect=self._prospect(company="Acme, save 50% guaranteed"),
                problem="backlogs", proof="demo", evidence_ids=["sig-1"])

    def test_missing_inputs_rejected(self):
        with self.assertRaises(ValueError):
            GA.draft_outreach(prospect={}, problem="x", proof="y", evidence_ids=["s"])
        with self.assertRaises(ValueError):
            GA.draft_outreach(prospect=self._prospect(), problem="",
                              proof="y", evidence_ids=["s"])
        with self.assertRaises(ValueError):
            GA.draft_outreach(prospect=self._prospect(), problem="x",
                              proof="y", evidence_ids=[])

    def test_brief_verified_fields_only(self):
        brief = GA.build_sales_brief(company="Acme", pain="backlogs",
                                     evidence_ids=["sig-1"])
        self.assertEqual(brief.next_action, "human_review_before_outreach")
        with self.assertRaises(ValueError):
            GA.build_sales_brief(company="", pain="x", evidence_ids=["s"])


class DedupeTests(unittest.TestCase):
    def test_duplicates_point_at_first(self):
        result = GA.dedupe_prospects([
            {"company": "Acme", "domain": "acme.com", "contact_name": "Sam"},
            {"company": "ACME Inc", "domain": "acme.com", "contact_name": "S."},
            {"company": "Beta LLC", "domain": "beta.co", "contact_name": "Jo"},
        ])
        self.assertEqual(result["kept_count"], 2)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["duplicates"][0]["duplicate_of_index"], 0)

    def test_malformed_rows_rejected(self):
        with self.assertRaises(ValueError):
            GA.dedupe_prospects("not-a-list")
        with self.assertRaises(ValueError):
            GA.dedupe_prospects([{"notes": "no identity here"}])


class CrmProposalTests(unittest.TestCase):
    def test_proposal_never_executes(self):
        proposal = GA.crm_overlay_proposal(entity_id="acc-1", stage="QUALIFIED",
                                           evidence_ids=["sig-1"], activity="log call")
        self.assertFalse(proposal["executed"])
        self.assertIn("approval", proposal["execution"])

    def test_missing_inputs_rejected(self):
        with self.assertRaises(ValueError):
            GA.crm_overlay_proposal(entity_id="", stage="X",
                                    evidence_ids=["s"], activity="a")
        with self.assertRaises(ValueError):
            GA.crm_overlay_proposal(entity_id="a", stage="X",
                                    evidence_ids=[], activity="a")


class SuppressionTests(unittest.TestCase):
    def test_suppressed_number_respected(self):
        from jarvis_control_plane.capabilities import suppression_check

        with tempfile.TemporaryDirectory() as tmp:
            supp_file = Path(tmp) / "suppressed.json"
            supp_file.write_text(json.dumps({"suppressed_phones": ["+15551234567"]}),
                                 encoding="utf-8")
            verdict = suppression_check({"phone": "(555) 123-4567"},
                                        supp_file)
            self.assertTrue(verdict["suppressed"])
            clean = suppression_check({"phone": "+15559876543"}, supp_file)
            self.assertFalse(clean["suppressed"])


class GtmRoutingTests(unittest.TestCase):
    def test_gtm_read_caps_route(self):
        for cap, stage in [
            ("market_research", "DISCOVER"),
            ("company_research", "RESEARCH"),
            ("lead_cleaning", "SCORE"),
            ("lead_qualification", "SCORE"),
            ("account_scoring", "SCORE"),
            ("offer_matching", "STRATEGY"),
            ("message_generation", "STRATEGY"),
            ("response_classification", "MEASURE"),
            ("sales_brief", "STRATEGY"),
            ("gtm_analytics", "MEASURE"),
        ]:
            with self.subTest(cap=cap):
                spec, _ = route_capability(cap, stage)
                self.assertEqual(spec.provider, "gtm")

    def test_gtm_controlled_write_needs_approval(self):
        for cap, stage in [("outreach_drafting", "PACKAGE"),
                           ("crm_update", "MEASURE"),
                           ("pipeline_management", "MEASURE")]:
            with self.subTest(cap=cap):
                with self.assertRaises(PermissionError):
                    route_capability(cap, stage)
                spec, _ = route_capability(
                    cap, stage, approval={"approved": True, "approver": "human"})
                self.assertEqual(spec.capability, cap)

    def test_gtm_send_never_routes(self):
        with self.assertRaises(PermissionError):
            route_capability("outreach_send", "PACKAGE",
                             approval={"approved": True, "approver": "human"})

    def test_gtm_deferred_never_route(self):
        for cap, stage in [("prospect_discovery", "DISCOVER"),
                           ("lead_enrichment", "RESEARCH")]:
            with self.subTest(cap=cap):
                with self.assertRaises(PermissionError):
                    route_capability(cap, stage)

    def test_gtm_skills_registered(self):
        from jarvis_control_plane.factory_skills import build_skill_registry

        names = {s.skill for s in build_skill_registry()}
        for required in ("icp_definition", "prospect_qualification",
                         "lead_cleaning", "evidence_verification",
                         "offer_matching", "outreach_writing",
                         "objection_handling", "proposal_preparation",
                         "crm_hygiene", "pipeline_review", "gtm_analytics",
                         "competitive_research", "market_research",
                         "account_research"):
            self.assertIn(required, names)

    def test_score_stage_lists_gtm_caps(self):
        caps = stage_capabilities("SCORE")
        for expected in ("lead_cleaning", "lead_qualification", "account_scoring"):
            self.assertIn(expected, caps)


if __name__ == "__main__":
    unittest.main()
