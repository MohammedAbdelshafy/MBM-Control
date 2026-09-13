from __future__ import annotations

from .contracts import BlockReason, BuyerEvidence, OfferPacket, PropertyEvidence, SendState


def _money(value: float) -> str:
    return f"${float(value):,.0f}"


def _buyer_matches(property_evidence: PropertyEvidence, buyer: BuyerEvidence | None, offer: float) -> tuple[list[BlockReason], bool]:
    reasons: list[BlockReason] = []
    if buyer is None:
        reasons.append(BlockReason.BUYER_MARKET_MISMATCH)
        return reasons, False
    markets = {str(value).strip().lower() for value in buyer.buy_box.get("markets", [])}
    max_purchase = float(buyer.buy_box.get("max_purchase") or 0)
    market_ok = property_evidence.city.strip().lower() in markets
    purchase_ok = offer <= max_purchase
    if not market_ok:
        reasons.append(BlockReason.BUYER_MARKET_MISMATCH)
    if not purchase_ok:
        reasons.append(BlockReason.BUYER_MAX_PURCHASE_EXCEEDED)
    return reasons, market_ok and purchase_ok


def build_offer_packet(property_evidence: PropertyEvidence, seller: dict[str, object], buyer: BuyerEvidence | None, underwriting: dict[str, object], offer_price: float) -> OfferPacket:
    if property_evidence.status != "ok":
        raise ValueError("property evidence is not usable")
    if buyer is not None and buyer.status != "ok":
        raise ValueError("buyer evidence is not usable")
    name = str(seller.get("name") or "Property owner")
    phone = str(seller.get("phone") or "")
    email = str(seller.get("email") or "")
    verified = bool(seller.get("contact_verified"))
    offer = float(offer_price)
    city = property_evidence.city
    address = property_evidence.address
    buyer_name = buyer.name if buyer else "matched buyer not yet selected"
    subject = f"Offer for {address}"
    email_copy = f"Subject: {subject}\n\nHello {name},\n\nI am interested in purchasing the property at {address} in {city} as-is. Based on the information currently available, my proposed purchase price is {_money(offer)}. Please reply if you would like to discuss the offer and next steps.\n\nThis message is an offer to discuss a transaction, not a claim about title, valuation, or closing terms."
    whatsapp_copy = f"Hi {name}, I’m interested in {address}. I’d like to discuss an as-is offer of {_money(offer)}. Would you be open to a quick call?"
    call_payload = {"name": name, "phone": phone, "email": email, "contact_verified": verified, "property": address, "offer": offer, "buyer_match": buyer_name}
    provenance = [{"source_url": property_evidence.source_url, "source_name": property_evidence.source_name, "status": property_evidence.status}]
    if buyer is not None:
        provenance.append({"source_url": buyer.source_url, "source_name": buyer.source_name, "status": buyer.status})

    blocked_reasons: list[BlockReason] = []
    if not verified:
        blocked_reasons.append(BlockReason.CONTACT_UNVERIFIED)
    buyer_reasons, buyer_ok = _buyer_matches(property_evidence, buyer, offer)
    blocked_reasons.extend(buyer_reasons)
    if underwriting.get("passes_economic_gate") is not True:
        blocked_reasons.append(BlockReason.ECONOMIC_GATE_FAILED)

    gate_ok = not blocked_reasons
    return OfferPacket(
        property=property_evidence,
        seller=dict(seller),
        buyer=buyer,
        underwriting=dict(underwriting),
        offer_price=offer,
        email_copy=email_copy,
        whatsapp_copy=whatsapp_copy,
        manual_call_payload=call_payload,
        send_state=SendState.HUMAN_SEND_REQUIRED if gate_ok else SendState.HUMAN_REVIEW_BLOCKED,
        blocked_reasons=blocked_reasons,
        source_provenance=provenance,
    )
