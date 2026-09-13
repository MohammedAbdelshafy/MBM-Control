from MBM.LeadEngine.real_estate.contracts import BlockReason, BuyerEvidence, PropertyEvidence, SendState
from MBM.LeadEngine.real_estate.deal_bridge import to_canonical_deal
from MBM.LeadEngine.real_estate.offer_builder import build_offer_packet
from MBM.LeadEngine.real_estate.underwriting import underwrite


PROPERTY = PropertyEvidence(
    address="123 Main St",
    city="Cleveland",
    state="OH",
    source_url="https://example.com/property/123",
    source_name="synthetic-property",
)

SELLER_VERIFIED = {"name": "Synthetic Seller", "phone": "+12165550123", "contact_verified": True}
SELLER_UNVERIFIED = {**SELLER_VERIFIED, "contact_verified": False}

BUYER_MATCH = BuyerEvidence(
    name="Cleveland buyer",
    source_url="https://example.com/investor-cleveland",
    source_name="synthetic-buyer",
    buy_box={"markets": ["Cleveland"], "max_purchase": 125000},
)
BUYER_MARKET_MISMATCH = BuyerEvidence(
    name="Phoenix buyer",
    source_url="https://example.com/investor-phoenix",
    source_name="synthetic-buyer",
    buy_box={"markets": ["Phoenix"], "max_purchase": 125000},
)
BUYER_MAX_MISMATCH = BuyerEvidence(
    name="Budget Cleveland buyer",
    source_url="https://example.com/investor-budget",
    source_name="synthetic-buyer",
    buy_box={"markets": ["Cleveland"], "max_purchase": 80000},
)


UNDERWRITING = underwrite(arv=200000, repairs=30000, purchase_price=70000)


def build_packet(seller, buyer=BUYER_MATCH, offer_price=85000, underwriting=UNDERWRITING):
    return build_offer_packet(PROPERTY, seller, buyer, underwriting, offer_price)


def test_clean_deal_passes_all_gates():
    packet = build_packet(SELLER_VERIFIED)
    assert packet.send_state is SendState.HUMAN_SEND_REQUIRED
    assert packet.blocked_reasons == []
    assert to_canonical_deal(packet).stage.value == "QUALIFIED"


def test_unverified_contact_blocks_independently():
    packet = build_packet(SELLER_UNVERIFIED)
    assert packet.send_state is SendState.HUMAN_REVIEW_BLOCKED
    assert packet.blocked_reasons == [BlockReason.CONTACT_UNVERIFIED]


def test_market_mismatch_blocks_independently():
    packet = build_packet(SELLER_VERIFIED, BUYER_MARKET_MISMATCH)
    assert packet.send_state is SendState.HUMAN_REVIEW_BLOCKED
    assert packet.blocked_reasons == [BlockReason.BUYER_MARKET_MISMATCH]


def test_max_purchase_mismatch_blocks_independently():
    packet = build_packet(SELLER_VERIFIED, BUYER_MAX_MISMATCH)
    assert packet.send_state is SendState.HUMAN_REVIEW_BLOCKED
    assert packet.blocked_reasons == [BlockReason.BUYER_MAX_PURCHASE_EXCEEDED]


def test_failed_economic_gate_blocks_independently():
    weak_underwriting = underwrite(arv=100000, repairs=20000, purchase_price=80000)
    packet = build_packet(SELLER_VERIFIED, underwriting=weak_underwriting)
    assert packet.send_state is SendState.HUMAN_REVIEW_BLOCKED
    assert packet.blocked_reasons == [BlockReason.ECONOMIC_GATE_FAILED]
    deal = to_canonical_deal(packet)
    assert deal.stage.value == "DISQUALIFIED"
    assert deal.outcome == "REJECTED"
