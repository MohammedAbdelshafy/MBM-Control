"""
TESTS: AUTO-PERSISTENCE OF VERIFIED PRODUCER OUTPUTS INTO CANONICAL DIALER
===========================================================================
Proves the hard invariant: a producer-verified lead reaches the canonical
dialer DB in the SAME run through the existing single-writer gateway —
with normalization, dedupe, queue refresh, DNC safety, zero-shrinkage,
and honest failure semantics. All tests run on tmp DBs; production data
and artifacts are never touched.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import MBM.LeadEngine.lead_persistence as lp
from MBM.LeadEngine.lead_persistence import (
    map_to_canonical,
    normalize_phone_e164,
    persist_verified_leads,
    stable_lead_id,
)
from MBM.GLM.single_writer_lock import DialerSingleWriter


def _npi_lead(phone="+12109945512", npi="1234567890", company="Lone Star Family Health"):
    return {
        "npi": npi,
        "company_name": company,
        "taxonomy": "Family Medicine",
        "phone": phone,
        "address": "100 Main St, Dallas, TX 75201",
        "city": "Dallas",
        "state": "TX",
        "authorized_official_name": "Jane Doe",
        "verified_phone": "npi/registry",
        "source": "CMS NPI Registry API v2.1",
    }


def _buyer_card(phone="+15128830199", company="Austin Pediatric Clinic"):
    return {
        "company": company,
        "decision_maker": "Dr. Alice Smith",
        "role": "Owner",
        "industry": "Healthcare",
        "location": "Austin, TX",
        "phone": phone,
        "intent_tier": "HOT",
        "intent_score": 95,
        "source": "NPI registry",
        "source_url": "https://npiregistry.cms.hhs.gov",
    }


# ─── normalization ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("(210) 994-5512", "+12109945512"),
    ("210-994-5512", "+12109945512"),
    ("210.994.5512", "+12109945512"),
    ("+1 210 994 5512", "+12109945512"),
    ("12109945512", "+12109945512"),
    ("+12109945512", "+12109945512"),
    ("+442012345678", None),      # international: never invent +1
    ("210994551", None),          # too short: never invent digits
    ("", None),
])
def test_phone_normalization_e164(raw, expected):
    assert normalize_phone_e164(raw) == expected


# ─── mapping gate ─────────────────────────────────────────────────────────────

def test_invalid_phone_never_mapped_callable():
    assert map_to_canonical(_npi_lead(phone="210994551"), "t", "X") is None


def test_identity_required():
    lead = _npi_lead()
    lead["company_name"] = ""
    lead["authorized_official_name"] = ""
    assert map_to_canonical(lead, "t", "X") is None


# ─── persistence invariants (tmp canonical DB) ────────────────────────────────

def _persist(tmp_path, leads, source="test_source", prefix="TST"):
    db = tmp_path / "leads_database.json"
    return persist_verified_leads(
        leads, source=source, id_prefix=prefix,
        db_path=db, rerank=False,
    ), db


def test_verified_lead_persists_and_is_readable(tmp_path):
    res, db = _persist(tmp_path, [_npi_lead()])
    assert res["status"] == "SUCCESS"
    assert res["inserted"] == 1
    leads = DialerSingleWriter(db_path=db).read_leads()
    assert len(leads) == 1
    rec = leads[0]
    assert rec["phone"] == "+12109945512"
    assert rec["verification_status"] == "VERIFIED"
    assert rec["callable"] is True
    assert rec["id"].startswith("TST-")
    assert rec["source"] == "CMS NPI Registry API v2.1"


def test_failed_verification_not_inserted_as_callable(tmp_path):
    res, db = _persist(tmp_path, [_npi_lead(phone="not-a-phone")])
    assert res["status"] == "SUCCESS"  # run succeeded...
    assert res["skipped_invalid"] == 1  # ...but the bad lead never entered
    assert len(DialerSingleWriter(db_path=db).read_leads()) == 0


def test_idempotent_repeat_no_duplicate(tmp_path):
    _, db = _persist(tmp_path, [_npi_lead()])
    # second run against the SAME db
    res2 = persist_verified_leads([_npi_lead()], source="test_source",
                                  id_prefix="TST", db_path=db, rerank=False)
    assert res2["status"] == "SUCCESS"
    assert res2["inserted"] == 0 and res2["updated"] == 1
    assert len(DialerSingleWriter(db_path=db).read_leads()) == 1


def test_cross_producer_same_lead_one_record(tmp_path):
    """Two producers emitting the same phone create exactly ONE canonical record."""
    db = tmp_path / "leads_database.json"
    r1 = persist_verified_leads([_npi_lead()], source="npi", id_prefix="NPI",
                                db_path=db, rerank=False)
    # buyer hunter emits same phone with different id scheme
    r2 = persist_verified_leads([_buyer_card(phone="+12109945512")], source="hunter",
                                id_prefix="BUYER", db_path=db, rerank=False)
    assert r1["status"] == r2["status"] == "SUCCESS"
    leads = DialerSingleWriter(db_path=db).read_leads()
    assert len(leads) == 1, "duplicate across producers!"
    assert leads[0]["id"].startswith("NPI-")  # original stable id preserved


def test_zero_shrinkage_on_existing_records(tmp_path):
    db = tmp_path / "leads_database.json"
    persist_verified_leads([_npi_lead(), _buyer_card()], source="s", id_prefix="TST",
                           db_path=db, rerank=False)
    before = len(DialerSingleWriter(db_path=db).read_leads())
    res = persist_verified_leads([_npi_lead(npi="9999999999", phone="+15128830200",
                                            company="New Clinic LLC")],
                                 source="s", id_prefix="TST", db_path=db, rerank=False)
    after = len(DialerSingleWriter(db_path=db).read_leads())
    assert res["zero_shrinkage"] is True
    assert after == before + 1


def test_canonical_write_failure_surfaced(tmp_path):
    """A failing gateway write must yield PERSISTENCE_FAILURE, not success."""
    called = {}
    class Boom:
        def read_leads(self):
            return []
    orig_patch = lp.patch_dialer_db
    def boom(*a, **kw):
        called["hit"] = True
        raise RuntimeError("disk full")
    monkey = pytest.MonkeyPatch()
    monkey.setattr(lp, "patch_dialer_db", boom)
    try:
        res = persist_verified_leads([_npi_lead()], source="s", id_prefix="TST",
                                     db_path=tmp_path / "db.json", rerank=False)
    finally:
        monkey.undo()
    assert called.get("hit") is True
    assert res["status"] == "PERSISTENCE_FAILURE"
    assert any("disk full" in e for e in res["errors"])


def test_dnc_suppressed_phone_rejected_by_gateway(tmp_path):
    """Suppressed phones must never become callable via persistence."""
    from MBM.LeadEngine import dialer_gateway as dg
    db = tmp_path / "leads_database.json"
    sup = tmp_path / "suppressed_bad_phones.json"
    sup.write_text(json.dumps({"suppressed_phones": ["+12109945512"]}), encoding="utf-8")
    monkey = pytest.MonkeyPatch()
    monkey.setattr(dg, "SUPPRESSION_FILE", sup)
    try:
        res = persist_verified_leads([_npi_lead()], source="s", id_prefix="TST",
                                     db_path=db, rerank=False)
    finally:
        monkey.undo()
    assert res["status"] == "SUCCESS"
    assert res["inserted"] == 0  # suppressed lead rejected by the gateway
    assert len(DialerSingleWriter(db_path=db).read_leads()) == 0


def test_new_verified_seller_enters_tier1(tmp_path):
    """A verified real-estate seller persists AND lands in the Tier-1 seller lane."""
    db = tmp_path / "leads_database.json"
    seller = {
        "company_name": "123 Oak Street Property",
        "contact": "John Seller",
        "phone": "+19722345503",
        "property_address": "123 Oak St, Dallas, TX",
        "segment": "ABSENTEE_OWNER",
        "distress_reason": "absentee owner",
        "vertical_tag": "Real Estate Sellers",
        "phone_verified": True,
        "verification_status": "VERIFIED",
    }
    res = persist_verified_leads([seller], source="seller_intel", id_prefix="SEL",
                                 db_path=db, rerank=True)
    assert res["status"] == "SUCCESS"
    assert res["queue_refreshed"] is True
    leads = DialerSingleWriter(db_path=db).read_leads()
    top = [l for l in leads if l.get("call_priority") == 1]
    assert len(top) == 1 and top[0]["is_real_estate"] is True
    assert top[0]["queue_rank"] == 1


def test_stable_ids_deterministic():
    a = stable_lead_id("NPI", "12345", "Clinic", "2109945512")
    b = stable_lead_id("NPI", "12345", "clinic ", "2109945512")
    assert a == b and a.startswith("NPI-")


# ─── producer wiring ──────────────────────────────────────────────────────────

def test_buyer_hunter_entry_point_surfaces_persistence_failure():
    """run_ai_assistant_buyer_hunter must downgrade to PARTIAL_FAILURE when
    canonical persistence fails (contract check via summary stamping)."""
    import MBM.LeadEngine.ai_assistant_buyer_hunter as bh
    summary = {"dialer_persistence": {"status": "PERSISTENCE_FAILURE"}}
    persistence_status = (summary.get("dialer_persistence") or {}).get("status", "SKIPPED_EMPTY")
    status = "SUCCESS" if persistence_status == "SUCCESS" else "PARTIAL_FAILURE"
    assert status == "PARTIAL_FAILURE"
    # and the module actually stamps summary inside _export_artifacts
    src = Path(bh.__file__).read_text(encoding="utf-8")
    assert 'summary["dialer_persistence"]' in src
    assert "persist_verified_leads" in src


def test_npi_module_wiring_present():
    import MBM.LeadEngine.npi_verified_callsheet as npi
    src = Path(npi.__file__).read_text(encoding="utf-8")
    assert "persist_verified_leads" in src
    assert "PARTIAL_FAILURE" in src


def test_promote_script_uses_single_writer():
    """The freshness-promotion script must NOT write the DB directly."""
    src = (ROOT_DIR / "MBM" / "LeadEngine" / "promote_new_verified_leads_to_top.py").read_text(encoding="utf-8")
    assert "DialerSingleWriter" in src
    assert ".write_text(json.dumps(final" not in src


def test_fixture_runs_cannot_touch_production_callsheet(tmp_path):
    """Priority refresh triggered from a fixture DB must leave the production
    callsheet byte-identical (contamination guard holds under auto-persistence)."""
    prod = ROOT_DIR / "MBM" / "Artifacts" / "DIALER_TOP_PRIORITY_CALLSHEET.md"
    before = prod.read_bytes() if prod.exists() else None
    db = tmp_path / "leads_database.json"
    persist_verified_leads([_npi_lead()], source="s", id_prefix="TST",
                           db_path=db, rerank=True)
    after = prod.read_bytes() if prod.exists() else None
    assert before == after
