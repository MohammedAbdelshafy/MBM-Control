from __future__ import annotations


def underwrite(arv: float, repairs: float, purchase_price: float, spread_target: float = 15000.0) -> dict[str, object]:
    arv = float(arv)
    repairs = max(0.0, float(repairs))
    purchase_price = max(0.0, float(purchase_price))
    spread_target = max(0.0, float(spread_target))
    mao = max(0.0, round(arv * 0.70 - repairs, 2))
    gross_spread = round(max(0.0, arv - purchase_price - repairs), 2)
    projected_spread = round(min(spread_target, gross_spread), 2)
    return {
        "arv": arv,
        "repairs": repairs,
        "purchase_price": purchase_price,
        "mao": mao,
        "gross_spread": gross_spread,
        "projected_spread": projected_spread,
        "passes_economic_gate": bool(arv > 0 and purchase_price > 0 and purchase_price <= mao),
    }


def qualifies_for_human_review(underwriting: dict[str, object], source_status: str, contact_verified: bool) -> bool:
    return (
        source_status == "ok"
        and contact_verified
        and underwriting.get("passes_economic_gate") is True
        and float(underwriting.get("gross_spread") or 0) > 0
    )
