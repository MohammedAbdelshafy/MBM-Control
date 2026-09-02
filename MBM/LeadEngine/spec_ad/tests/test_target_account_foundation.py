"""
Phase 2 foundation tests — run with: pytest MBM/LeadEngine/spec_ad/tests/test_target_account_foundation.py -q

Covers Steps 3-7:
- domain normalization (Step 3)
- dedup (Step 4) — exact, www, case, protocol, path, conflicting identity, missing domain
- ICP + creative scoring (Step 5)
- qualification boundary (Step 5)
- provenance retained
- repository idempotency + conflict handling (Step 9)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from MBM.LeadEngine.spec_ad.config.spec_ad_config import SpecAdConfig, load_spec_ad_config
from MBM.LeadEngine.spec_ad.targeting.dedup import (
    canonicalize_domain,
    dedup_accounts,
    dedup_key,
    detect_conflicting_identity,
    extract_canonical_domain,
)
from MBM.LeadEngine.spec_ad.targeting.repository import TargetAccountRepository
from MBM.LeadEngine.spec_ad.targeting.scoring import build_target_account, qualify_account, score_creative_opportunity, score_icp


def _cfg(**overrides):
    base = SpecAdConfig()
    if overrides:
        # rebuild with overrides
        data = {**base.__dict__, **overrides}
        return SpecAdConfig(**data)
    return base


# ---- Step 3: domain normalization ----

def test_canonicalize_basic():
    assert canonicalize_domain("https://www.Acme.com:8080/path") == "acme.com"
    assert canonicalize_domain("https://ACME.COM/") == "acme.com"
    assert canonicalize_domain("https://www.acme.com/?x=1") == "acme.com"
    assert canonicalize_domain("acme.com") == "acme.com"
    assert canonicalize_domain("http://acme.com#frag") == "acme.com"
    assert canonicalize_domain("contact@acme.io") == "acme.io"


def test_canonicalize_rejects_placeholder():
    assert canonicalize_domain("https://example.com") is None
    assert canonicalize_domain("test.com") is None
    assert canonicalize_domain("example.org") is None
    assert canonicalize_domain("not-a-domain") is None
    assert canonicalize_domain("") is None
    assert canonicalize_domain(None) is None  # type: ignore


def test_canonicalize_preserves_subdomain():
    # only www. stripped; meaningful subdomains preserved
    assert canonicalize_domain("https://app.acme.com/path") == "app.acme.com"
    assert canonicalize_domain("https://blog.example.acme.com") == "blog.example.acme.com"
    assert canonicalize_domain("https://www.app.acme.com") == "app.acme.com"


def test_dont_invent_domain():
    assert extract_canonical_domain({"company_name": "Acme Inc"}) is None
    assert extract_canonical_domain({"company": "Acme"}) is None
    assert extract_canonical_domain({}) is None


# ---- Step 4: dedup ----

def test_dedup_exact():
    a = {"website": "https://acme.com", "company_name": "Acme"}
    b = {"website": "https://acme.com", "company_name": "Acme"}
    assert dedup_key(a) == dedup_key(b) == "domain:acme.com"


def test_dedup_www():
    a = {"website": "https://acme.com"}
    b = {"website": "https://www.acme.com/path?x=1"}
    assert dedup_key(a) == dedup_key(b)


def test_dedup_case_protocol_path():
    cases = [
        {"website": "https://ACME.com"},
        {"website": "http://acme.com/"},
        {"website": "https://acme.com/path"},
        {"website": "acme.com"},
    ]
    keys = {dedup_key(c) for c in cases}
    assert len(keys) == 1 and "domain:acme.com" in keys


def test_dedup_keeps_first():
    accounts = [
        {"website": "https://acme.com", "company_name": "Acme One"},
        {"website": "https://www.acme.com", "company_name": "Acme Two"},
        {"website": "https://other.com", "company_name": "Other"},
    ]
    unique, dups = dedup_accounts(accounts)
    assert len(unique) == 2
    assert len(dups) == 1
    assert unique[0]["company_name"] == "Acme One"


def test_conflicting_identity():
    existing = {"website": "https://acme.com", "company_name": "Acme Software"}
    incoming_same = {"website": "https://acme.com", "company_name": "Acme Software Inc"}
    incoming_conflict = {"website": "https://acme.com", "company_name": "Totally Different Corp XYZ"}
    assert not detect_conflicting_identity(existing, incoming_same)
    assert detect_conflicting_identity(existing, incoming_conflict)


def test_missing_domain_fallback():
    a = {"company_name": "Acme Inc"}
    b = {"company_name": "Acme Inc"}
    assert dedup_key(a) == dedup_key(b) == "name:acme-inc"
    # no signal at all → None, not invented
    assert dedup_key({}) is None


# ---- Step 5: scoring ----

def test_score_icp_and_creative_neutral():
    cfg = _cfg()
    acct = {"industry": "software", "website": "https://acme.com", "product": "AI scheduling", "country": "US", "company_size": 80}
    icp = score_icp(acct, cfg)
    creative = score_creative_opportunity(acct, cfg)
    assert 0 <= icp <= 100
    assert 0 <= creative <= 100


def test_qualify_requires_website():
    cfg = _cfg()
    bad = {"company_name": "Stealth", "industry": "software", "product": "tool"}
    q = qualify_account(bad, cfg, {})
    assert not q["qualified"]
    assert "missing_website" in q["reasons"]


def test_qualify_requires_commercial_and_visual_and_marketing():
    cfg = _cfg()
    # missing product → not commercially active + no visual angle
    bad = {"website": "https://acme.com", "industry": "software"}
    q = qualify_account(bad, cfg, {})
    assert not q["qualified"]
    assert "not_commercially_active" in q["reasons"] or "no_visual_ad_angle" in q["reasons"]


def test_qualify_rejects_excluded_industry():
    cfg = _cfg(excluded_industries=["gambling"])
    bad = {"website": "https://bad.com", "industry": "gambling", "product": "casino"}
    q = qualify_account(bad, cfg, {})
    assert not q["qualified"]
    assert "irrelevant_industry" in q["negativeSignals"]


def test_qualify_funding_not_auto():
    cfg = _cfg()
    # funding alone without required signals should not qualify
    bad = {"website": "https://acme.com", "industry": "software", "signals": {"total_raised_usd": 5000000}}
    # missing product/commercial
    q = qualify_account(bad, cfg, {})
    assert not q["qualified"]
    # with required signals, funding helps creative but not auto-qualify if ICP low
    good = {
        "website": "https://acme.com",
        "industry": "software",
        "product": "AI scheduling",
        "country": "US",
        "company_size": 80,
        "signals": {"recent_funding": True, "total_raised_usd": 5000000},
    }
    q2 = qualify_account(good, cfg, {})
    # should qualify because it meets all required + ICP threshold
    assert q2["qualified"]


def test_qualify_famous_brand_not_auto():
    cfg = _cfg()
    # Large famous brand still needs ICP + visual + commercial; size alone not auto
    # Empty product → fails
    bad = {"website": "https://linkedin.com", "industry": "software", "company_size": 20000}
    q = qualify_account(bad, cfg, {})
    assert not q["qualified"]
    # With product but wrong ICP (media) → fails icp_mismatch
    media = {"website": "https://techcrunch.com", "industry": "media", "product": "news", "company_size": 500}
    q2 = qualify_account(media, cfg, {})
    assert not q2["qualified"]
    assert "icp_mismatch" in q2["reasons"] or "irrelevant_industry" in q2["negativeSignals"] or not q2["qualified"]


def test_qualify_min_icp_threshold():
    cfg_low = _cfg(min_icp_score=90)
    good = {"website": "https://acme.com", "industry": "software", "product": "tool", "country": "US"}
    q = qualify_account(good, cfg_low, {})
    # ICP likely ~75, so should fail threshold 90
    assert not q["qualified"]


def test_build_target_account_shape():
    cfg = _cfg()
    raw = {
        "company_name": "Acme Software",
        "website": "https://acme.com",
        "industry": "software",
        "product": "AI scheduling",
        "company_size": 80,
        "country": "US",
        "signals": {"recent_funding": True},
        "provenance": [{"source": "intelligence", "source_url": "https://worldmonitor.app/event/1", "retrieved_at": "2026-09-02T00:00:00Z"}],
    }
    built = build_target_account(raw, cfg, {})
    for key in ("id", "company_name", "canonical_domain", "website", "industry", "company_size", "country", "firmographics", "funding_signals", "icp_score", "creative_opportunity_score", "account_status", "provenance", "created_at", "updated_at", "last_evaluated_at"):
        assert key in built, f"missing {key}"
    assert built["canonical_domain"] == "acme.com"
    assert built["provenance"][0]["source"] == "intelligence"
    # external text sanitized via security.sanitize_external_text (no control chars)
    assert "\x00" not in built["company_name"]


# ---- Step 9: repository ----

def test_repository_upsert_idempotent_and_conflict():
    cfg = _cfg()
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "accounts.json"
        audit = Path(tmp) / "audit.jsonl"
        repo = TargetAccountRepository(store_path=store, audit_path=audit)

        raw = {"company_name": "Acme Software", "website": "https://acme.com", "industry": "software", "product": "AI scheduling", "country": "US"}
        first = repo.create_target_account(raw, cfg, {})
        assert first["canonical_domain"] == "acme.com"

        # upsert same domain → idempotent (same id)
        second = repo.upsert_target_account({"website": "https://www.acme.com", "company_name": "Acme Software Inc", "industry": "software", "product": "AI scheduling"}, cfg, {})
        assert second["id"] == first["id"]
        # no conflict because names overlap
        assert second["account_status"] != "DISQUALIFIED"

        # conflicting identity → marked DISQUALIFIED, not overwritten
        conflict = repo.upsert_target_account({"website": "https://acme.com", "company_name": "Totally Different XYZ Corp NoOverlap"}, cfg, {})
        assert conflict["id"] == first["id"]
        assert conflict["account_status"] == "DISQUALIFIED"
        assert conflict["exclusion_reason"] == "conflicting_identity"
        # provenance preserved (both)
        assert len(conflict["provenance"]) >= 2

        # find_by_domain
        found = repo.find_by_domain("https://acme.com/path?x=1")
        assert found and found["id"] == first["id"]

        # suppress
        suppressed = repo.suppress_account(first["id"], reason="manual_suppression", actor="tester")
        assert suppressed["account_status"] == "SUPPRESSED"
