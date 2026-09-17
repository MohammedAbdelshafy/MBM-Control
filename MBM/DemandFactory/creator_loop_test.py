import unittest

from creator_loop import CreatorProfile, build_creator_pack, qualify_creator


class CreatorLoopTests(unittest.TestCase):
    def test_creator_qualification_requires_fit(self):
        creator = CreatorProfile(
            creator_id="creator-1",
            name="Example Creator",
            audience_description="construction operators",
            audience_fit=0.9,
            trust_fit=0.8,
            commercial_fit=0.7,
            content_fit=0.9,
            reach=0.4,
        )
        self.assertTrue(qualify_creator(creator))

    def test_creator_pack_contains_tracking_and_feedback(self):
        creator = CreatorProfile(
            creator_id="creator-2",
            name="Example Creator",
            audience_description="contractors",
            audience_fit=0.9,
            trust_fit=0.9,
            commercial_fit=0.9,
            content_fit=0.8,
            reach=0.5,
        )
        pack = build_creator_pack(
            creator,
            opportunity_id="opp-1",
            product_id="prod-1",
            hook="Cut estimating time",
            audience_problem="estimating takes too long",
            demonstrated_outcome="produce a first estimate faster",
            proof_assets=["demo-1"],
            creative_assets=["reel-1", "hero-1"],
        )
        self.assertEqual(pack.tracking_key, "creator:creator-2:product:prod-1")
        self.assertTrue(pack.disclosure_required)
        self.assertEqual(len(pack.creator_feedback_questions), 3)


if __name__ == "__main__":
    unittest.main()
