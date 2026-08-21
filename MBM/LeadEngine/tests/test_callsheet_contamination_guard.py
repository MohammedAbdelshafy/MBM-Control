"""
TESTS: CALLSHEET CONTAMINATION GUARD
 =============================================================================
 Regression guards proving that fixture/test runs of the priority engine
 NEVER overwrite production artifacts:

 1. A non-canonical (fixture) DB refresh with --apply must not touch
    MBM/Artifacts/DIALER_TOP_PRIORITY_CALLSHEET.md or the refresh audit.
 2. A canonical-context refresh still exports the callsheet + audit.
 3. Ranking invariants remain intact (count preserved, DNC excluded,
    deterministic order, seller Tier-1).
 =============================================================================
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import MBM.LeadEngine.dialer_priority_engine as engine_mod
from MBM.LeadEngine.dialer_priority_engine import (
    DialerPriorityEngine,
    _is_canonical_db,
    refresh_dialer_priority_queue,
)


def _make_lead(lead_id, phone, **kw):
    base = {
        "id": lead_id,
        "phone": phone,
        "company": kw.pop("company", "Test Property Co"),
        "contact": kw.pop("contact", "Owner " + lead_id[-3:]),
        "vertical": kw.pop("vertical", "Real Estate Sellers"),
        "property_address": kw.pop("property_address", "100 Test St, Dallas, TX"),
        "phone_verified": True,
        "verification_status": "VERIFIED",
        "created_at": "2026-08-20T10:00:00+00:00",
    }
    base.update(kw)
    return base


def _write_db(path, leads):
    path.write_text(json.dumps(leads), encoding="utf-8")
    return path


def test_is_canonical_db_detection():
    assert _is_canonical_db(engine_mod.DIALER_DB_PATH) is True
    assert _is_canonical_db(Path("C:/nonexistent/fixture/leads.json")) is False


def test_fixture_apply_never_touches_production_callsheet(tmp_path):
    """THE regression: fixture --apply must leave production artifacts byte-identical."""
    prod_callsheet = ROOT_DIR / "MBM" / "Artifacts" / "DIALER_TOP_PRIORITY_CALLSHEET.md"
    before = prod_callsheet.read_bytes() if prod_callsheet.exists() else None

    fixture_db = _write_db(tmp_path / "leads.json", [
        _make_lead("RE_001", "+12109945512"),
        _make_lead("B2B_001", "+19725551111", vertical="Digital Services"),
        _make_lead("DNC_001", "+12133324440", identity_state="DO_NOT_CALL"),
    ])
    res = refresh_dialer_priority_queue(
        db_path=fixture_db,
        sales_ledger_path=tmp_path / "ledger.json",
        dry_run=False,
    )
    assert res["status"] == "SUCCESS"

    after = prod_callsheet.read_bytes() if prod_callsheet.exists() else None
    assert before == after, "Fixture run overwrote the production callsheet!"


def test_non_canonical_context_skips_artifact_export(tmp_path, monkeypatch):
    """Even with artifact paths pointed at writable sentinels, a fixture DB
    refresh must NOT create them."""
    sentinel_callsheet = tmp_path / "sentinel_callsheet.md"
    sentinel_audit = tmp_path / "sentinel_audit.json"
    monkeypatch.setattr(engine_mod, "CALLSHEET_MD_PATH", sentinel_callsheet)
    monkeypatch.setattr(engine_mod, "AUDIT_LOG_PATH", sentinel_audit)

    fixture_db = _write_db(tmp_path / "leads.json", [
        _make_lead("RE_001", "+12109945512"),
        _make_lead("B2B_001", "+19725551111", vertical="Digital Services"),
    ])
    res = refresh_dialer_priority_queue(
        db_path=fixture_db,
        sales_ledger_path=tmp_path / "ledger.json",
        dry_run=False,
    )
    assert res["status"] == "SUCCESS"
    assert not sentinel_callsheet.exists(), "Fixture run exported a callsheet!"
    assert not sentinel_audit.exists(), "Fixture run wrote a refresh audit!"


def test_canonical_context_still_exports(tmp_path, monkeypatch):
    """When the active DB IS canonical (simulated via redirected constants),
    apply must regenerate callsheet + audit with correct content."""
    canonical_copy = tmp_path / "canonical" / "leads_database.json"
    canonical_copy.parent.mkdir(parents=True)
    _write_db(canonical_copy, [
        _make_lead("RE_001", "+12109945512"),
        _make_lead("RE_002", "+15128830199"),
        # B2B lead: NO property address (a property address is an RE signal).
        _make_lead("B2B_001", "+19725551111", vertical="Digital Services",
                   property_address="", company="Cold Software LLC"),
        _make_lead("DNC_001", "+12133324440", identity_state="DO_NOT_CALL"),
    ])
    out_callsheet = tmp_path / "out_callsheet.md"
    out_audit = tmp_path / "out_audit.json"
    monkeypatch.setattr(engine_mod, "DIALER_DB_PATH", canonical_copy)
    monkeypatch.setattr(engine_mod, "CALLSHEET_MD_PATH", out_callsheet)
    monkeypatch.setattr(engine_mod, "AUDIT_LOG_PATH", out_audit)

    res = refresh_dialer_priority_queue(
        db_path=canonical_copy,
        sales_ledger_path=tmp_path / "ledger.json",
        dry_run=False,
    )
    assert res["status"] == "SUCCESS"
    assert out_callsheet.exists(), "Canonical apply did not export the callsheet!"
    text = out_callsheet.read_text(encoding="utf-8")
    assert "TOP REAL ESTATE SELLERS" in text
    assert "Total Verified Records:** 4" in text
    assert out_audit.exists()
    audit = json.loads(out_audit.read_text(encoding="utf-8"))
    assert audit["total_records"] == 4
    assert audit["real_estate_seller_leads"] == 2


def test_ranking_invariants_preserved_under_guard(tmp_path):
    """Count preservation, DNC exclusion, Tier-1 seller top rank, determinism."""
    engine = DialerPriorityEngine(sales_ledger_path=tmp_path / "ledger.json")
    leads = [
        # Distinct motivation so RE_TOP unambiguously tops the tier.
        _make_lead("RE_TOP", "+12109945512", segment="DISTRESSED_SELLER", motivation_score=80),
        _make_lead("RE_002", "+15128830199"),
        # B2B lead: NO property address (a property address is an RE signal).
        _make_lead("B2B_001", "+19725551111", vertical="Digital Services",
                   property_address="", company="Cold Software LLC"),
        _make_lead("DNC_001", "+12133324440", identity_state="DO_NOT_CALL"),
        _make_lead("BAD_001", "12345"),  # invalid phone -> suppressed
    ]
    r1 = engine.rank_leads([dict(l) for l in leads])
    r2 = engine.rank_leads([dict(l) for l in leads])

    assert len(r1) == len(leads) == 5, "Zero-shrinkage violated"
    callable_ids = [l["id"] for l in r1 if l.get("is_callable")]
    assert "DNC_001" not in callable_ids and "BAD_001" not in callable_ids
    assert r1[0]["id"] == "RE_TOP" and r1[0]["call_priority"] == 1
    assert [l["queue_rank"] for l in r1 if l.get("is_callable")] == \
           [l["queue_rank"] for l in r2 if l.get("is_callable")], "Non-deterministic ordering"
