import pytest
from MBM.ProductizedOffers.catalog import get_catalog
from MBM.ProductizedOffers.schema import ProductizedOffer

def test_catalog_structure():
    catalog = get_catalog()
    assert len(catalog) == 4
    
    for offer in catalog:
        assert isinstance(offer, ProductizedOffer)
        # Verify required fields from the issue
        assert offer.offer_id
        assert offer.name
        assert offer.target_market
        assert offer.buyer_role
        assert offer.customer_job
        assert offer.problem_trigger
        assert offer.promised_outcome
        assert "Hypothesis:" in offer.promised_outcome # Ensure it's a hypothesis
        assert offer.scope
        assert len(offer.deliverables) > 0
        assert offer.proof_asset
        assert offer.entry_offer_price > 0
        assert offer.core_implementation_price > 0
        assert len(offer.qualification_criteria) > 0
        assert len(offer.rejection_criteria) > 0
        assert offer.approval_requirement
        assert offer.payment_path
        assert offer.success_metric
        assert offer.retention_path
        
def test_validation_motion():
    catalog = get_catalog()
    offer = catalog[0]
    
    # Should not validate if any criteria are missing
    assert not offer.validate_motion(demo_exists=False, qualified_accounts=20, approved_assets=True)
    assert offer.state == "draft"
    
    assert not offer.validate_motion(demo_exists=True, qualified_accounts=19, approved_assets=True)
    assert offer.state == "draft"
    
    # Should validate when all criteria are met
    assert offer.validate_motion(demo_exists=True, qualified_accounts=20, approved_assets=True)
    assert offer.state == "validated"
