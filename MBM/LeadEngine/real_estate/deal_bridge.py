from __future__ import annotations

from .contracts import OfferPacket, SendState


def to_canonical_deal(packet: OfferPacket):
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealStage, DealType
    qualified = packet.send_state is SendState.HUMAN_SEND_REQUIRED
    return CanonicalDeal(
        id=f"RE-{abs(hash(packet.property.address)):08x}",
        deal_type=DealType.PROPERTY,
        lead_id=f"RE-{abs(hash(packet.property.address)):08x}",
        source=packet.property.source_name,
        source_url=packet.property.source_url,
        owner_name=str(packet.seller.get("name") or ""),
        contact_phone=str(packet.seller.get("phone") or ""),
        vertical="Distressed Real Estate",
        city=packet.property.city,
        state=packet.property.state,
        property_address=packet.property.address,
        calculated_mao=float(packet.underwriting.get("mao") or 0),
        estimated_repair_cost=float(packet.underwriting.get("repairs") or 0),
        starting_bid=float(packet.underwriting.get("purchase_price") or 0),
        primary_offer=f"${packet.offer_price:,.0f}",
        stage=DealStage.QUALIFIED if qualified else DealStage.DISQUALIFIED,
        outcome="PENDING" if qualified else "REJECTED",
        reason=("Evidence/contact gate passed" if qualified else "; ".join(reason.value for reason in packet.blocked_reasons)),
        next_action="HUMAN_SEND" if qualified else "RESEARCH",
        evidence_provenance=packet.source_provenance,
    )
