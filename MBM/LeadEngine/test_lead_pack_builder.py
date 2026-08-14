"""
test_lead_pack_builder -- standalone tests for the MBM Lead Pack Builder.

Covers: contact verification, no-fabrication rules, gate blocking, tiering,
CSV export, manifest output contract, Whop product spec.
Run:  python test_lead_pack_builder.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lead_pack_builder import (  # noqa: E402
    EMAIL_RE,
    WHOP_PRODUCT,
    build_pack,
    build_pack_lead,
    export_csv,
    ingest,
    write_brief,
    write_whop_config,
    _valid_email,
    _valid_phone,
)

PASS = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAILURES
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL {name} {detail}")


VERIFIED_RE = {
    "deal_id": "RE-1",
    "contact_name": "JANE DOE",
    "company_name": "Doe Holdings LLC",
    "property_address": "123 Main St, Cleveland, OH",
    "city": "Cleveland",
    "state": "OH",
    "phone": "+12165550123",
    "email": "jane@example.com",
    "skip_trace_status": "VERIFIED",
    "verified_source": "skip_trace_verified",
    "motivation_score": 80,
    "motivation_signals": ["foreclosure", "absentee"],
    "vertical": "Real Estate Sellers",
}

UNVERIFIED = {
    "deal_id": "RE-2",
    "contact_name": "JOHN SMITH",
    "phone": "+12165550124",
    "skip_trace_status": "UNVERIFIED",
    "vertical": "Real Estate Sellers",
}

NO_CONTACT = {
    "deal_id": "RE-3",
    "contact_name": "GHOST LLC",
    "skip_trace_status": "VERIFIED",
    "vertical": "Real Estate Sellers",
}


def test_validation() -> None:
    print("contact validation")
    check("valid email accepted", _valid_email("a@b.co") == "a@b.co")
    check("bad email rejected", _valid_email("not-an-email") == "")
    check("valid phone kept", _valid_phone("+12165550123") == "+12165550123")
    check("short phone rejected", _valid_phone("12345") == "")
    check("email regex", bool(EMAIL_RE.match("jane.doe+tag@example.com")))


def test_no_fabrication() -> None:
    print("no-fabrication rules")
    lead = build_pack_lead(NO_CONTACT)
    check("no invented email", lead.email == "")
    check("no invented phone", lead.phone == "")
    check("not contact_ok", not lead.contact_ok)
    check("excluded reason present", "no deliverable contact" in lead.reason)


def test_verified_lead() -> None:
    print("verified lead inclusion")
    lead = build_pack_lead(VERIFIED_RE)
    check("phone extracted", lead.phone == "+12165550123")
    check("email extracted", lead.email == "jane@example.com")
    check("contact_ok", lead.contact_ok)
    check("verification source", lead.verification_source == "skip_trace_verified")
    check("quality scored non-zero", lead.quality_score > 0)
    check("pack tier not D for high-quality verified", lead.pack_tier in ("A", "B", "C"))


def test_unverified_excluded() -> None:
    print("unverified exclusion")
    lead = build_pack_lead(UNVERIFIED)
    check("has phone", bool(lead.phone))
    check("not contact_ok", not lead.contact_ok)
    check("reason flags unverified", "unverified" in lead.reason)


def test_gate_blocking(tmpdir: Path) -> None:
    print("gate blocking")
    rows = [VERIFIED_RE, UNVERIFIED, NO_CONTACT]  # 1 of 3 verified = 33%
    src = tmpdir / "q.json"
    src.write_text(json.dumps(rows), encoding="utf-8")
    report = build_pack(src, gate=0.80)
    check("blocked below gate", report["status"] == "blocked")
    check("gate applied", report["gated"] is False)
    check("pct 0.3333", abs(report["contact_verification_pct"] - 0.3333) < 0.001)
    check("only verified in leads", len(report["leads"]) == 1)
    check("excluded counted", len(report["excluded"]) == 2)


def test_gate_pass(tmpdir: Path) -> None:
    print("gate pass")
    rows = [VERIFIED_RE, UNVERIFIED]  # 1 of 2 = 50%
    src = tmpdir / "q2.json"
    src.write_text(json.dumps(rows), encoding="utf-8")
    report = build_pack(src, gate=0.40)
    check("ready above low gate", report["status"] == "ready")
    check("gated true", report["gated"] is True)


def test_csv_export(tmpdir: Path) -> None:
    print("csv export")
    lead = build_pack_lead(VERIFIED_RE)
    out = tmpdir / "pack.csv"
    export_csv([lead], out)
    text = out.read_text(encoding="utf-8")
    check("header present", "pack_tier" in text)
    check("lead present", "JANE DOE" in text)
    check("phone present", "+12165550123" in text)


def test_brief_and_whop(tmpdir: Path) -> None:
    print("brief + whop spec")
    rows = [VERIFIED_RE, UNVERIFIED, NO_CONTACT]
    src = tmpdir / "q3.json"
    src.write_text(json.dumps(rows), encoding="utf-8")
    report = build_pack(src, gate=0.80)
    brief = tmpdir / "brief.md"
    write_brief(report, brief)
    check("brief writes", brief.exists())
    check("blocked noted", "BLOCKED" in brief.read_text(encoding="utf-8"))
    whop = tmpdir / "whop.json"
    write_whop_config(report, whop)
    spec = json.loads(whop.read_text(encoding="utf-8"))
    check("whop product name", spec["name"] == WHOP_PRODUCT["name"])
    check("whop price 899", spec["price_usd"] == 899)


def test_ingest_csv(tmpdir: Path) -> None:
    print("csv ingest")
    csv_path = tmpdir / "buyers.csv"
    csv_path.write_text(
        "contact_name,email,phone,Status\n"
        "ACME,Bob,bob@acme.com,+12165550123,New\n",
        encoding="utf-8",
    )
    rows = ingest(csv_path)
    check("csv parsed", len(rows) == 1)
    check("csv header mapped", rows[0]["contact_name"] == "ACME")


def test_manifest_contract(tmpdir: Path) -> None:
    print("manifest output contract")
    from lead_pack_builder import main
    src = tmpdir / "q4.json"
    src.write_text(json.dumps([VERIFIED_RE]), encoding="utf-8")
    manifest_out = tmpdir / "m.json"
    rc = main([
        "--apply", "--source", str(src), "--gate", "0.50",
        "--whop-config",
    ])
    check("exit 0", rc == 0)
    packs = list((Path(__file__).resolve().parent / "artifacts" / "lead_packs").glob("lead_pack_*_manifest.json"))
    check("manifest written", len(packs) >= 1)
    if packs:
        m = json.loads(packs[-1].read_text(encoding="utf-8"))
        check("manifest status ready", m["status"] == "ready")
        check("manifest has outputs", "csv" in m["outputs"])
        check("manifest owner system", m["owner"] == "system")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="leadpack_test_")
    tmpdir = Path(tmp)
    test_validation()
    test_no_fabrication()
    test_verified_lead()
    test_unverified_excluded()
    test_gate_blocking(tmpdir)
    test_gate_pass(tmpdir)
    test_csv_export(tmpdir)
    test_brief_and_whop(tmpdir)
    test_ingest_csv(tmpdir)
    test_manifest_contract(tmpdir)

    print(f"\nResult: {PASS} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print(f"  FAILED: {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())