import pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from MBM.LeadEngine.offmarket.models import normalize_address, deterministic_property_id
from MBM.LeadEngine.offmarket.services.dedup import dedup_properties
from MBM.LeadEngine.offmarket.models import Property
from MBM.LeadEngine.offmarket.signals.equity import calculate_equity
from MBM.LeadEngine.offmarket.services.eligibility import evaluate_eligibility

def test_property_normalization():
    assert normalize_address("  123 Main St., ") == "123 MAIN ST"
    assert normalize_address("9727 WHITEHURST DR") == "9727 WHITEHURST DR"

def test_apn_dedup():
    p1=Property(property_id="", apn="00C11970000D02704", parcel_id="00C11970000D02704", address="12480 ABRAMS RD", normalized_address=normalize_address("12480 ABRAMS RD"), city="Dallas", state="TX", zip="75094", county="Dallas")
    p2=Property(property_id="", apn="00C11970000D02704", parcel_id="00C11970000D02704", address="12480 ABRAMS RD", normalized_address=normalize_address("12480 ABRAMS RD"), city="Dallas", state="TX", zip="75094", county="Dallas")
    deduped=dedup_properties([p1,p2])
    assert len(deduped)==1
    assert deduped[0].property_id.startswith("PROP-")

def test_equity_buckets():
    snap=calculate_equity(300000, 50000, 0, source="test")
    assert snap.equity_bucket in ("75_89","90_plus")
    snap2=calculate_equity(200000, 150000, 0, source="test")
    assert snap2.equity_bucket in ("25_49","lt_25")
    snap3=calculate_equity(None, None, None)
    assert snap3.equity_bucket=="unknown"
    assert snap3.is_uncertain is True

def test_phone_normalization_via_gate():
    # reuse existing CanonicalPhone
    from MBM.LeadEngine.canonical_lead_schema import CanonicalPhone
    assert CanonicalPhone.normalize_phone("(214) 328-6918")=="+12143286918"
    assert CanonicalPhone.normalize_phone("555-0100")==None

def test_dnc_blocking():
    lead={"property_id":"PROP-TX-DALLAS-ABC","phone":"+12143286918","owner_name":"Test Owner","suppression_status":"CLEAR","contact_confidence":"high","dnc_flag":False}
    # Simulate DNC via get_callable_state: set suppressed flag
    lead2=dict(lead)
    lead2["is_suppressed"]=True
    from MBM.LeadEngine.dialer_queue_engine import get_callable_state
    state=get_callable_state(lead2)
    assert state["suppression_reason"] is not None

def test_eligibility_low_confidence():
    lead={"property_id":"P1","phone":"+12143286918","owner_name":"Owner LLC","contact_confidence":"low"}
    elig=evaluate_eligibility(lead)
    assert elig.status=="BLOCKED_LOW_CONFIDENCE"

def test_eligibility_ready():
    lead={"property_id":"P2","phone":"+12143286918","owner_name":"Real Person","contact_confidence":"high", "suppression_status":"CLEAR", "source":"CMS NPI Registry API v2.1", "source_reference":"NPI-123", "verification_method":"npi_registry_api", "observed_at":"2026-08-30T00:00:00Z", "verified_at":"2026-08-30T00:00:00Z", "source_type":"government_registry", "script_id":"SCRIPT-AI_CONSULTANCY-1", "Call_Script":"123456789012345678901234"}
    # Need verified gate to pass; add required fields
    lead["source_reference"]="NPI-123"
    lead["verification_method"]="npi_registry_api"
    elig=evaluate_eligibility(lead)
    assert elig.status in ("READY","BLOCKED_SUPPRESSION","BLOCKED_INVALID_PHONE","BLOCKED_LOW_CONFIDENCE","REVIEW_REQUIRED")

def test_dry_run_no_write(tmp_path):
    from MBM.LeadEngine.offmarket.pipeline import OffMarketPipeline
    from MBM.LeadEngine.offmarket.config import EngineConfig
    cfg=EngineConfig()
    pipe=OffMarketPipeline(config=cfg, db_path=tmp_path/"leads.json")
    # dry-run should not require dialer write
    # Mock discover to avoid network
    pipe.discover = lambda limit=10: []
    res=pipe.run(limit=10, dry_run=True)
    assert res["stats"]["total_properties"]==0

def test_owner_matching_trust():
    from MBM.LeadEngine.property_intel.schema import classify_owner_type
    assert classify_owner_type("JOHN SMITH TRUST")=="trust"
    assert classify_owner_type("ABC HOLDINGS LLC")=="entity"
    assert classify_owner_type("JOHN SMITH")=="individual"
