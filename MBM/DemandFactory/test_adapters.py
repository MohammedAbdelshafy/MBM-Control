import unittest

from .adapters.higgsfield import HiggsfieldCreativeAdapter
from .adapters.hubspot import HubSpotCommercialAdapter
from .adapters.knowledge_graph import NullKnowledgeGraphAdapter


class AdapterTests(unittest.TestCase):
    def test_knowledge_graph_validates_relationships(self):
        adapter = NullKnowledgeGraphAdapter()
        result = adapter.record_relationships("opp-1", [{"source": "demand", "target": "offer", "description": "maps"}])
        self.assertEqual(result["status"], "proposed")
        with self.assertRaises(ValueError):
            adapter.record_relationships("opp-1", [{"source": "demand"}])

    def test_hubspot_adapter_is_proposal_only(self):
        adapter = HubSpotCommercialAdapter()
        payload = adapter.build_deal_payload(
            {"opportunity_id": "opp-1", "problem": "pricing", "buyer_segment": "contractors", "distributor_type": "creator", "state": "ready_to_launch", "expected_value": 1.2, "confidence": 0.9},
            {"offer_id": "offer-1", "format": "toolkit", "price": 49, "distribution_probability": 0.8},
        )
        self.assertEqual(payload["object_type"], "DEAL")
        self.assertIn("offer_id", payload["properties"])
        self.assertFalse(payload.get("executed", False))

    def test_higgsfield_requires_claim_mapping(self):
        adapter = HiggsfieldCreativeAdapter()
        plan = adapter.build_asset_plan({"claims": ["save 2 hours"], "objections": ["Will this fit my workflow?"]})
        self.assertGreaterEqual(len(plan), 4)
        self.assertTrue(all(item.get("claim") or item.get("objection") for item in plan))
        with self.assertRaises(ValueError):
            adapter.build_asset_plan({"claims": []})


if __name__ == "__main__":
    unittest.main()
