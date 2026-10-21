import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "MBM" / "LeadEngine"))

from waste_buyer_os.matching import match_buyer, rank_buyers
from waste_buyer_os.models import BuyerProfile, FactoryWasteQuota
from waste_buyer_os.search_spec import build_search_spec


def test_material_normalization_and_search_spec():
    quota = FactoryWasteQuota(material="EVA foam", kg_per_month=12000, form="offcuts")
    spec = build_search_spec(quota)

    assert spec["material_canonical"] == "eva_foam"
    assert spec["source_rail"]["name"] == "Dawar"
    assert any("eva" in query.lower() for query in spec["web_queries"])


def test_evidence_backed_exact_material_match():
    quota = FactoryWasteQuota(material="rubber", kg_per_month=5000, form="scrap")
    buyer = BuyerProfile(
        company_name="Example Rubber Recycler",
        geography="Egypt",
        buyer_categories=("rubber recycler",),
        accepted_materials=("rubber",),
        accepted_forms=("scrap",),
        evidence_urls=("https://example.com/materials",),
    )

    result = match_buyer(quota, buyer)

    assert result.score >= 0.9
    assert result.qualified
    assert "material match: rubber" in result.reasons


def test_unverified_buyer_cannot_be_qualified():
    quota = FactoryWasteQuota(material="EVA foam", kg_per_month=2500, form="offcuts")
    buyer = BuyerProfile(
        company_name="Unverified Trader",
        geography="Egypt",
        accepted_materials=("EVA foam",),
        accepted_forms=("offcuts",),
    )

    result = match_buyer(quota, buyer)

    assert not result.qualified
    assert "public evidence URL" in result.missing_checks


def test_rank_prefers_qualified_and_higher_score():
    quota = FactoryWasteQuota(material="cardboard", kg_per_month=3000, form="baled")
    qualified = BuyerProfile(
        company_name="Verified Paper Recycler",
        geography="Egypt",
        buyer_categories=("cardboard recycler",),
        accepted_materials=("cardboard",),
        accepted_forms=("baled",),
        evidence_urls=("https://example.com",),
    )
    weaker = BuyerProfile(
        company_name="Generic Recycler",
        geography="Egypt",
        accepted_materials=("paper",),
        evidence_urls=("https://example.com",),
    )

    ranked = rank_buyers(quota, [weaker, qualified])
    assert ranked[0].buyer.company_name == "Verified Paper Recycler"
    assert ranked[0].qualified
