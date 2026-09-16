import pytest
from MBM.DemandFactory.compiler import ProductCompiler, ProductSpec, ValidationFailure
from MBM.DemandFactory.adapters.openai_agent import OpenAIAgentAdapter
from MBM.DemandFactory.engine import DemandFactory

def test_compiler_validates_spec():
    compiler = ProductCompiler()
    spec = ProductSpec(
        spec_version="1.0",
        product_id="prod_123",
        target_market="Test Market",
        deliverables=["asset_1"],
        capabilities=["content_generation"],
        permissions_required=[]
    )
    plan = compiler.compile(spec, dry_run=True)
    assert plan.product_id == "prod_123"
    assert len(plan.plan_hash) == 64
    assert plan.is_dry_run is True

def test_compiler_rejects_unsafe_permissions():
    compiler = ProductCompiler()
    spec = ProductSpec(
        spec_version="1.0",
        product_id="prod_123",
        target_market="Test Market",
        deliverables=[],
        capabilities=[],
        permissions_required=["production_database_write"]
    )
    with pytest.raises(ValidationFailure, match="Unsafe permission requested"):
        compiler.compile(spec)

def test_engine_executes_build():
    engine = DemandFactory()
    spec = ProductSpec(
        spec_version="1.0",
        product_id="prod_123",
        target_market="Test Market",
        deliverables=["test_asset"],
        capabilities=["content_generation"],
        permissions_required=[]
    )
    adapter = OpenAIAgentAdapter()
    result = engine.execute_build(spec, adapter, dry_run=True)
    
    assert result["status"] == "success"
    assert result["plan_id"].startswith("plan_")
    assert "stub_asset_for_test_asset" in result["result"]["materialized_assets"]
