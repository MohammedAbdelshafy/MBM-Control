from pathlib import Path

from productized_service.factory import build_customer_pack, load_offer


def test_build_customer_pack_excludes_private_payment_metadata(tmp_path: Path) -> None:
    offer = tmp_path / "ai-consultancy-sprint"
    offer.mkdir()
    (offer / "landing.html").write_text("<html>offer</html>", encoding="utf-8")
    (offer / "whop_manifest.json").write_text(
        '{"offer":"AI Consultancy Sprint","items":{"sprint_audit":{"amount":297,"checkout_url":"https://whop.com/checkout/plan_x"}}}',
        encoding="utf-8",
    )
    (offer / "neteller_manifest.json").write_text(
        '{"wallet_email":"private@example.com","wallet_account":"SECRET","items":{"x":{"amount":1}}}',
        encoding="utf-8",
    )
    (offer / "delivery").mkdir()
    (offer / "delivery" / "audit.md").write_text("audit template", encoding="utf-8")

    result = build_customer_pack(offer, tmp_path / "out")

    assert "delivery/audit.md" in result["files"]
    assert not (tmp_path / "out" / "neteller_manifest.json").exists()
    public = (tmp_path / "out" / "catalog.json").read_text(encoding="utf-8")
    assert "private@example.com" not in public
    assert "SECRET" not in public


def test_load_offer_reports_delivery_readiness_from_real_assets(tmp_path: Path) -> None:
    offer = tmp_path / "ai-consultancy-sprint"
    offer.mkdir()
    (offer / "landing.html").write_text("<html>offer</html>", encoding="utf-8")
    (offer / "whop_manifest.json").write_text(
        '{"offer":"AI Consultancy Sprint","items":{"sprint_audit":{"amount":297,"checkout_url":"https://whop.com/checkout/plan_x"}}}',
        encoding="utf-8",
    )
    (offer / "delivery").mkdir()
    (offer / "delivery" / "README.md").write_text("delivery", encoding="utf-8")

    data = load_offer(offer)

    assert data["engineering_ready"] is True
    assert data["delivery_ready"] is True
    assert data["payment_ready"] is True
    assert data["commercially_validated"] is False


def test_canonical_ai_sprint_offer_has_a_customer_delivery_pack() -> None:
    root = Path(__file__).resolve().parents[2]
    offer = root / "productized-service" / "ai-consultancy-sprint"
    data = load_offer(offer)
    assert data["customer_ready"] is True
    assert data["delivery_files"] == sorted(
        [
            "delivery/01_ai_growth_audit.md",
            "delivery/02_five_sales_scripts.md",
            "delivery/03_lead_map_template.csv",
            "delivery/04_72h_implementation_plan.md",
            "delivery/README.md",
        ]
    )
