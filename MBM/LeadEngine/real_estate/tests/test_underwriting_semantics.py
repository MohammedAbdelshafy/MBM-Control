from MBM.LeadEngine.real_estate.underwriting import underwrite


def test_margin_and_spread_definition_are_pinned():
    result = underwrite(200000, 30000, 70000, target_margin=0.65)
    assert result["target_margin"] == 0.65
    assert result["mao"] == 100000
    assert result["gross_spread"] == 100000
    assert result["gross_spread_definition"] == "ARV - purchase_price - repairs"
