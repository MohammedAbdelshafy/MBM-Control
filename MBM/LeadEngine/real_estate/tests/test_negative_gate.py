from MBM.LeadEngine.real_estate.contracts import BuyerEvidence, PropertyEvidence, SendState
from MBM.LeadEngine.real_estate.deal_bridge import to_canonical_deal
from MBM.LeadEngine.real_estate.offer_builder import build_offer_packet
from MBM.LeadEngine.real_estate.underwriting import underwrite, qualifies_for_human_review


def test_non_overlapping_buyer_and_unverified_seller_are_rejected():
    prop = PropertyEvidence(address="123 Main St", city="Cleveland", state="OH", source_url="https://example.com/property/123", source_name="synthetic-property")
    buyer = BuyerEvidence(name="Non-overlap buyer", source_url="https://example.com/investor-west", source_name="synthetic-buyer", buy_box={"markets": ["Phoenix"], "max_purchase": 125000})
    seller = {"name": "Synthetic Seller", "contact_verified": False}
    underwriting = underwrite(arv=200000, repairs=30000, purchase_price=70000)
    packet = build_offer_packet(prop, seller, buyer, underwriting, 85000)
    deal = to_canonical_deal(packet)
    assert qualifies_for_human_review(underwriting, prop.status, False) is False
    assert packet.send_state is SendState.HUMAN_REVIEW_BLOCKED
    assert deal.stage.value == "DISQUALIFIED"
    assert deal.outcome == "REJECTED"
