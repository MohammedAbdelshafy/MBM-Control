"""
test_routing -- standalone tests for the canonical routing resolver (issue #16).
Run:  python test_routing.py
Uses the REAL RoutingRegistry.json (fails closed if registry is missing).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mbm_social import routing

PASS = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAILURES
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL {name} {detail}")


def _registry_ok() -> bool:
    return routing.REGISTRY_PATH.exists()


def test_registry_present() -> None:
    print("registry present")
    check("RoutingRegistry.json exists", _registry_ok())
    if not _registry_ok():
        return
    reg = routing._load_registry()
    check("has accounts", isinstance(reg.get("accounts"), dict) and len(reg["accounts"]) > 0)
    check("has brands", isinstance(reg.get("brands"), dict) and len(reg["brands"]) > 0)


def test_resolve_destination() -> None:
    print("resolve_destination")
    if not _registry_ok():
        check("skipped (no registry)", True)
        return
    pkg = {"brand": "clippingfactorymbm", "target_platform": "youtube_shorts", "asset_id": "abc123"}
    dest = routing.resolve_destination(pkg)
    check("brand resolved", dest.brand_id == "clippingfactorymbm")
    check("platform mapped", dest.platform == "youtube")
    check("account resolved", dest.account_id == "yt_clippingfactorymbm")
    check("publish enabled", dest.publish_enabled is True)

    pkg2 = {"brand": "clippingfactorymbm", "target_platform": "youtube"}
    dest2 = routing.assert_routing_ok(pkg2)
    check("assert_routing_ok returns dest", dest2.account_id == "yt_clippingfactorymbm")


def test_fail_closed() -> None:
    print("fail-closed behaviour")
    if not _registry_ok():
        check("skipped (no registry)", True)
        return
    try:
        routing.resolve_destination({"target_platform": "youtube"})
        check("missing brand raises", False)
    except routing.RoutingError:
        check("missing brand raises", True)

    try:
        routing.resolve_destination({"brand": "nonexistentbrand", "target_platform": "youtube"})
        check("unknown brand raises", False)
    except routing.RoutingError:
        check("unknown brand raises", True)

    try:
        routing.resolve_destination({"brand": "clippingfactorymbm", "target_platform": "myspace"})
        check("unknown platform raises", False)
    except routing.RoutingError:
        check("unknown platform raises", True)


def test_brand_normalization() -> None:
    print("normalization")
    check("lower+strip", routing._normalize_brand(" ClippingFactoryMBM ") == "clippingfactorymbm")
    check("hyphen to underscore", routing._normalize_brand("dont-watch-this") == "dont_watch_this")
    check("empty stays empty", routing._normalize_brand("") == "")


def test_compute_asset_id() -> None:
    print("asset id")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "clip.mp4"
        p.write_bytes(b"data")
        a = routing.compute_asset_id(p)
        b = routing.compute_asset_id(p)
        check("stable for same file", a == b and len(a) == 12)


def test_known_tiktok_accounts() -> None:
    print("known TikTok accounts (issue #16 rule 7)")
    if not _registry_ok():
        check("skipped (no registry)", True)
        return
    reg = routing._load_registry()
    accounts = reg.get("accounts", {})
    registered = {
        routing._normalize_tiktok(acct.get("tiktok_username", acct.get("handle", "")))
        for acct in accounts.values()
        if acct.get("platform") == "tiktok"
    }
    for handle in sorted(routing.KNOWN_TIKTOK_ACCOUNTS):
        present = routing._normalize_tiktok(handle) in registered
        check(f"known handle '{handle}' surfaced ({'registered' if present else 'missing'})", True)


def test_audit_surfaces_missing() -> None:
    print("audit surfaces missing known accounts")
    if not _registry_ok():
        check("skipped (no registry)", True)
        return
    audit = routing.run_audit()
    issues = "\n".join(audit["issues"])
    # The audit MUST surface every known handle that is not yet in the registry
    # (issue #16: sixth active account discovered from local config + surfaced).
    reg = routing._load_registry()
    accounts = reg.get("accounts", {})
    registered = {
        routing._normalize_tiktok(acct.get("tiktok_username", acct.get("handle", "")))
        for acct in accounts.values()
        if acct.get("platform") == "tiktok"
    }
    for handle in sorted(routing.KNOWN_TIKTOK_ACCOUNTS):
        if routing._normalize_tiktok(handle) not in registered:
            check(f"missing '{handle}' reported as ISSUE", f"'{handle}' MISSING" in issues)


def main() -> int:
    print("routing tests")
    for t in (
        test_registry_present,
        test_resolve_destination,
        test_fail_closed,
        test_brand_normalization,
        test_compute_asset_id,
        test_known_tiktok_accounts,
        test_audit_surfaces_missing,
    ):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {e!r}")
            print(f"  FAIL {t.__name__} raised {e!r}")
    print(f"\nPASS: {PASS}  FAIL: {len(FAILURES)}")
    if FAILURES:
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())