"""
routing -- Canonical routing resolver for MBM-Social.

RESOLVE DESTINATION BEFORE PUBLISHING. Publish by account_id, never filename parsing.
Fails closed if destination is missing or ambiguous.

Usage:
  from mbm_social import routing
  dest = routing.resolve_destination(package)   # -> RoutingDestination or raises
  routing.assert_routing_ok(package)            # raises RoutingError if invalid
  routing.run_dry_run()                         # prints every asset + destination
  routing.run_audit()                           # prints audit report
"""
from __future__ import annotations

import json
import sys
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "RoutingRegistry.json"
QUEUE_DIR = ROOT / "publish_queue"


class RoutingError(Exception):
    """Raised when routing cannot be resolved or is ambiguous."""
    pass


@dataclass
class RoutingDestination:
    asset_id: str
    brand_id: str
    account_id: str
    platform: str
    channel: str
    profile_dir: str
    auth_method: str
    publish_enabled: bool

    def to_log_line(self) -> str:
        status = "ENABLED" if self.publish_enabled else "DISABLED"
        return (
            f"{self.asset_id:30s} | {self.brand_id:20s} | {self.platform:12s} | "
            f"{self.account_id:25s} | {self.channel:25s} | {status}"
        )


_REGISTRY_CACHE: dict | None = None
_ACCOUNT_BY_SLUG: dict[str, str] | None = None
_ASSET_CACHE: dict[str, dict] | None = None


def _load_registry() -> dict:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        _REGISTRY_CACHE = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return _REGISTRY_CACHE


def _accounts() -> dict[str, dict]:
    return _load_registry().get("accounts", {})


def _brands() -> dict[str, dict]:
    return _load_registry().get("brands", {})


def _platform_defaults() -> dict[str, str]:
    return _load_registry().get("platform_defaults", {})


def _normalize_brand(value: str) -> str:
    if not value:
        return ""
    return str(value).strip().lower().replace(" ", "").replace("-", "_")


def _normalize_tiktok(value: str) -> str:
    if not value:
        return ""
    cleaned = str(value).strip().lower().replace(" ", "").replace("-", "_")
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    if cleaned.startswith("tiktok_"):
        cleaned = cleaned[8:]
    return cleaned


def compute_asset_id(filepath: Path) -> str:
    """Generate a stable asset_id from the package filepath."""
    try:
        stat = filepath.stat()
        raw = f"{filepath.name}:{stat.st_size}:{stat.st_mtime_ns}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
    except Exception:
        return hashlib.sha256(str(filepath).encode()).hexdigest()[:12]


def resolve_target_platform(package: dict) -> str:
    """
    Determine the target platform from the package's target_platform field.
    Maps 'youtube_shorts' -> 'youtube', 'instagram_reels' -> 'instagram', etc.
    """
    target = package.get("target_platform") or package.get("platform") or "youtube"
    defaults = _platform_defaults()
    if target in defaults:
        return defaults[target]
    target_norm = _normalize_brand(target)
    for key, val in defaults.items():
        if _normalize_brand(key) == target_norm:
            return val
    return target_norm or "youtube"


def resolve_brand_id(package: dict) -> str:
    """Resolve the normalized brand_id from a package, with verification."""
    brand_raw = package.get("brand") or package.get("brand_id") or package.get("slug") or ""
    if not brand_raw:
        raise RoutingError(
            f"Package has no 'brand' field; cannot route without explicit brand assignment."
        )
    brand = _normalize_brand(brand_raw)

    brands = _brands()
    if brand not in brands:
        raise RoutingError(
            f"Brand '{brand_raw}' (normalized: '{brand}') is not in RoutingRegistry. "
            f"Known brands: {sorted(brands.keys())}. "
            f"Add it to RoutingRegistry.json before publishing."
        )
    return brand


def find_account_for(brand_id: str, platform: str) -> dict:
    """
    Find the canonical account_id for a brand+platform combo.
    Uses the explicit account mapping. Fails closed if not found.
    """
    platform_map = {
        "youtube": f"yt_{brand_id}",
        "tiktok": f"tt_{brand_id}",
        "instagram": f"ig_{brand_id}",
    }
    account_id = platform_map.get(platform)
    if not account_id:
        raise RoutingError(f"Unknown platform '{platform}'; expected youtube/tiktok/instagram.")

    accounts = _accounts()
    if account_id not in accounts:
        raise RoutingError(
            f"No account_id '{account_id}' for brand '{brand_id}' on '{platform}'. "
            f"Known accounts: {sorted(accounts.keys())}. "
            f"Add the account to RoutingRegistry.json."
        )
    return accounts[account_id]


def resolve_destination(package: dict, filepath: Optional[Path] = None) -> RoutingDestination:
    """
    Resolve the canonical routing destination for a package.
    This is the PRIMARY routing function called before any publish.

    Steps:
    1. Resolve brand_id from package (fail closed if missing/unknown)
    2. Resolve target platform from package
    3. Look up canonical account_id for brand+platform
    4. Verify publish_enabled
    5. Return fully resolved destination
    """
    brand_id = resolve_brand_id(package)
    platform = resolve_target_platform(package)

    account_info = find_account_for(brand_id, platform)

    # Cross-check: verify brand_id matches account's brand_id
    acct_brand = _normalize_brand(account_info.get("brand_id", ""))
    if acct_brand != brand_id:
        raise RoutingError(
            f"Account '{account_info.get('account_id')}' is owned by brand '{acct_brand}', "
            f"not '{brand_id}'. Account mapping mismatch in RoutingRegistry."
        )

    # Cross-check: verify platform matches account's platform
    acct_platform = account_info.get("platform", "").strip().lower()
    if acct_platform != platform:
        raise RoutingError(
            f"Account '{account_info.get('account_id')}' platform is '{acct_platform}', not '{platform}'."
        )

    if not account_info.get("publish_enabled", False):
        raise RoutingError(
            f"Account '{account_info.get('account_id')}' has publish_enabled=false. "
            f"Enable before publishing."
        )

    asset_id = package.get("asset_id") or package.get("package_id") or \
               (compute_asset_id(filepath) if filepath else hashlib.sha256(
                   json.dumps(package, sort_keys=True).encode()).hexdigest()[:12])

    return RoutingDestination(
        asset_id=asset_id,
        brand_id=brand_id,
        account_id=account_info["account_id"],
        platform=platform,
        channel=account_info.get("youtube_channel_id") or account_info.get("handle") or account_info.get("tiktok_username") or "",
        profile_dir=account_info.get("profile_dir", ""),
        auth_method=account_info.get("auth_method", "unknown"),
        publish_enabled=account_info.get("publish_enabled", False),
    )


def assert_routing_ok(package: dict, filepath: Optional[Path] = None) -> RoutingDestination:
    """
    Assert that routing is valid BEFORE publishing.
    Raises RoutingError if destination is missing or ambiguous.
    Must be called immediately before any upload.
    """
    dest = resolve_destination(package, filepath)
    if not dest.account_id:
        raise RoutingError("Routing resolved but account_id is empty - cannot publish to an ambiguous destination.")
    return dest


def _load_queue_packages() -> list[tuple[Path, dict]]:
    """Load all draft packages from publish_queue."""
    packages = []
    for filepath in QUEUE_DIR.glob("*.json"):
        try:
            pkg = json.loads(filepath.read_text(encoding="utf-8"))
            if pkg.get("status") == "draft":
                packages.append((filepath, pkg))
        except Exception as e:
            print(f"  [ROUTING] Skipping unreadable {filepath.name}: {e}")
    return packages


def run_dry_run() -> list[dict]:
    """
    Show every asset and its exact destination. NO publishing happens.
    Output format: VIDEO | BRAND | PLATFORM | ACCOUNT | CHANNEL | STATUS
    """
    print("=" * 100)
    print("ROUTING DRY-RUN — every asset and its canonical destination")
    print("=" * 100)
    print(f"VIDEO{' ' * 30} | BRAND{' ' * 16} | PLATFORM{' ' * 2} | ACCOUNT{' ' * 18} | CHANNEL{' ' * 18} | STATUS")
    print("-" * 100)

    results = []
    packages = _load_queue_packages()

    for filepath, pkg in sorted(packages, key=lambda x: x[0].name):
        video_path = pkg.get("video_path", pkg.get("clip_file_path", ""))
        video_name = Path(video_path).name[:35] if video_path else "NO VIDEO"

        try:
            dest = resolve_destination(pkg, filepath)
            status = "ROUTED" if dest.publish_enabled else "DISABLED"
            line = dest.to_log_line().replace(dest.asset_id, video_name)
            print(f"{video_name:35s} | {dest.brand_id:20s} | {dest.platform:12s} | {dest.account_id:25s} | {dest.channel:25s} | {status}")
            results.append({
                "video": video_name,
                "brand": dest.brand_id,
                "platform": dest.platform,
                "account": dest.account_id,
                "channel": dest.channel,
                "asset_id": dest.asset_id,
                "status": status,
                "filepath": str(filepath),
            })
        except RoutingError as e:
            status = "ERROR"
            print(f"{video_name:35s} | {pkg.get('brand', '?'):20s} | ???{'':9s} | {'UNROUTABLE':25s} | {'?':25s} | {status} — {e}")
            results.append({
                "video": video_name,
                "brand": pkg.get("brand", "?"),
                "platform": "???",
                "account": "UNROUTABLE",
                "channel": "?",
                "status": status,
                "error": str(e),
                "filepath": str(filepath),
            })

    print("-" * 100)
    total = len(results)
    routed = sum(1 for r in results if r["status"] == "ROUTED")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    disabled = sum(1 for r in results if r["status"] == "DISABLED")
    print(f"TOTAL: {total} | ROUTED: {routed} | ERRORS: {errors} | DISABLED: {disabled}")
    print("=" * 100)

    if errors > 0:
        print("\nROUTING ERRORS — fix these before publishing:")
        for r in results:
            if r["status"] == "ERROR":
                print(f"  ✗ {r['filepath']}: {r.get('error', 'unknown')}")

    return results


def run_audit() -> dict:
    """
    Audit the routing registry and queue for consistency:
    - Every brand in queue has a registry entry
    - Every active brand has accounts for all platforms
    - No orphaned packages without routing info
    - All profiles exist on disk
    """
    print("=" * 80)
    print("ROUTING AUDIT")
    print("=" * 80)

    registry = _load_registry()
    accounts = registry.get("accounts", {})
    brands_reg = registry.get("brands", {})
    issues = []
    passed = []

    # 1. Check every brand in ChannelRegistry/BrandRegistry is in accounts
    for brand_id in sorted(brands_reg.keys()):
        brand = brands_reg[brand_id]
        platforms = brand.get("social_handles", {})
        expected_accounts = []
        for platform in ("youtube", "tiktok", "instagram"):
            acct_id = f"{platform[0] * 2}_{brand_id}"  # yt_brand, tt_brand, ig_brand
            prefix = platform[0] * 2  # "yt", "tt", "ig"
            acct_id = f"{prefix}_{brand_id}"
            if acct_id not in accounts:
                issues.append(f"Brand '{brand_id}' missing account '{acct_id}' for platform '{platform}'")
            else:
                # Verify profile dir exists
                acct = accounts[acct_id]
                profile_dir = acct.get("profile_dir", "")
                if profile_dir:
                    full_path = ROOT / profile_dir
                    if not full_path.exists():
                        issues.append(f"Account '{acct_id}' profile dir does not exist: {full_path}")
                    else:
                        passed.append(f"Account '{acct_id}' profile exists: {profile_dir}")
                passed.append(f"Account '{acct_id}' registered for '{platform}'")

    # 2. Check every draft package has a resolvable route
    packages = _load_queue_packages()
    for filepath, pkg in packages:
        try:
            resolve_destination(pkg, filepath)
            passed.append(f"Package {filepath.name}: routed OK")
        except RoutingError as e:
            issues.append(f"Package {filepath.name}: {e}")

    # 3. Check for orphaned accounts (in registry but no profile on disk)
    for acct_id, acct in accounts.items():
        profile_dir = acct.get("profile_dir", "")
        if profile_dir:
            full_path = ROOT / profile_dir
            if not full_path.exists():
                issues.append(f"Account '{acct_id}' profile missing: {full_path}")

    print(f"\nChecks passed: {len(passed)}")
    print(f"Issues found: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"  [{i}] ISSUE: {issue}")
    for p in passed:
        print(f"  [OK] {p}")

    print("\n" + "=" * 80)
    return {"passed": passed, "issues": issues}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="MBM-Social routing resolver")
    parser.add_argument("command", choices=["dry-run", "audit", "resolve"], help="Command to run")
    parser.add_argument("--brand", help="Filter by brand slug")
    parser.add_argument("--package", help="Resolve routing for a specific package file")
    args = parser.parse_args(argv)

    if args.command == "dry-run":
        results = run_dry_run()
        errors = sum(1 for r in results if r["status"] == "ERROR")
        return 1 if errors > 0 else 0

    elif args.command == "audit":
        audit = run_audit()
        return 1 if audit["issues"] else 0

    elif args.command == "resolve":
        if args.package:
            pkg_path = Path(args.package)
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        else:
            print("Specify --package <path>")
            return 1
        try:
            dest = assert_routing_ok(pkg, pkg_path)
            print(f"Routing OK: {dest.account_id} ({dest.platform}) -> {dest.channel}")
            print(f"  asset_id: {dest.asset_id}")
            print(f"  brand_id: {dest.brand_id}")
            print(f"  profile_dir: {dest.profile_dir}")
            print(f"  auth_method: {dest.auth_method}")
            return 0
        except RoutingError as e:
            print(f"Routing FAILED: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())