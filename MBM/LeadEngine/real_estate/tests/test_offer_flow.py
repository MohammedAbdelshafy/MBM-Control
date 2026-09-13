import pytest

from MBM.LeadEngine.real_estate.contracts import BuyerEvidence, PropertyEvidence, OfferPacket
from MBM.LeadEngine.real_estate.underwriting import underwrite, qualifies_for_human_review
from MBM.LeadEngine.real_estate.offer_builder import build_offer_packet
from MBM.LeadEngine.real_estate.deal_bridge import to_canonical_deal


PROPERTY = PropertyEvidence(
    address="123 Main St",
    city="Cleveland",
    state="OH",
    source_url="https://example.com/property/123",
    source_name="example-listing",
    status="ok",
    fields={"arv": 200000},
)

BUYER = BuyerEvidence(
    name="Example Investor LLC",
    source_url="https://example.com/investor",
    source_name="public-business-profile",
    status="ok",
    buy_box={"markets": ["Cleveland"], "max_purchase": 125000},
    contact={"email": "investor@example.com"},
)

SELLER = {
    "name": "Example Seller",
    "phone": "+12165550123",
    "email": "seller@example.com",
    "contact_verified": True,
}


UNDERWRITING = underwrite(arv=200000, repairs=30000, purchase_price=70000)


def test_underwrite_calculates_mao_and_economic_gate():
    assert UNDERWRITING["mao"] == 110000
    assert UNDERWRITING["gross_spread"] == 130000
    assert UNDERWRITING["passes_economic_gate"] is True
    assert qualifies_for_human_review(UNDERWRITING, "ok", True) is True


def test_build_offer_packet_is_manual_send_only():
    packet = build_offer_packet(PROPERTY, SELLER, BUYER, UNDERWRITING, 85000)
    assert packet.send_state == "HUMAN_SEND_REQUIRED"
    assert "85,000" in packet.whatsapp_copy
    assert "85,000" in packet.email_copy
    assert packet.manual_call_payload["phone"] == "+12165550123"


def test_offer_packet_rejects_missing_provenance():
    with pytest.raises(ValueError, match="source_url"):
        OfferPacket.from_mapping({"property": {"address": "123 Main St"}})


def test_bridge_maps_to_canonical_property_deal():
    packet = build_offer_packet(PROPERTY, SELLER, BUYER, UNDERWRITING, 85000)
    deal = to_canonical_deal(packet)
    assert deal.deal_type.value == "property"
    assert deal.stage.value == "QUALIFIED"
    assert deal.primary_offer == "$85,000"
    assert deal.contact_phone == "+12165550123"
    assert deal.source_url == "https://example.com/property/123"
