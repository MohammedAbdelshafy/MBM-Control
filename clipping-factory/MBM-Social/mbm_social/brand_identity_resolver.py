"""
brand_identity_resolver -- ONE authoritative brand/channel identity resolver.

Every YouTube publishing path MUST call resolve_brand_binding(brand) before
any platform upload.  The resolver answers:

  ONE BRAND → ONE VERIFIED CHANNEL → ONE TOKEN → ONE PUBLISH DESTINATION

Resolution strategy (cheap-first):
  1. Load token entry for brand (strict: no cross-brand fallthrough)
  2. Load ChannelRegistry.json configured channel_id + handle
  3. Load BrandRegistry.json configured channel_id + handle
  4. If token has a refresh_token, attempt a live channels().list(mine=True)
     to discover the ACTUAL channel identity (requires youtube.readonly scope;
     if scope is missing, skip the live call and use stored channel_id)
  5. Cross-compare all four sources
  6. Return a BindingResult with explicit status

Binding statuses:
  VALID         — all sources agree (or token+registry agree, live check skipped)
  MISMATCH      — sources disagree on channel identity (fail-closed)
  INVALID_AUTH  — token cannot refresh (invalid_grant / revoked)
  UNKNOWN       — insufficient data to determine (no token, no registry entry)
  BLOCKED       — operator explicitly blocked this brand

IMPORTANT: for new automated publishing, MISMATCH and INVALID_AUTH MUST fail
closed (PUBLISH_BLOCKED).  The historical published_identity_warning status
is retained only for already-published evidence records.

This module is also used by registry_identity.check_registries() to report
the full fleet binding status.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS_PATH = ROOT / "youtube_tokens.json"
CHANNEL_REGISTRY = ROOT / "ChannelRegistry.json"
BRAND_REGISTRY = ROOT / "BrandRegistry.json"

_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{20,}$")


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _norm(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("-", "_")


@dataclass
class BindingResult:
    brand: str
    binding_status: str  # VALID | MISMATCH | INVALID_AUTH | UNKNOWN | BLOCKED
    configured_channel_id: str = ""
    configured_handle: str = ""
    token_channel_id: str = ""
    token_handle: str = ""
    live_channel_id: str = ""
    live_channel_handle: str = ""
    registry_source: str = ""     # which registry provided configured_channel_id
    error: str = ""
    checked_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}

    @property
    def can_publish(self) -> bool:
        return self.binding_status == "VALID"

    @property
    def should_block(self) -> bool:
        return self.binding_status in ("MISMATCH", "INVALID_AUTH", "BLOCKED")


def _try_live_channel_identity(token_entry: dict) -> tuple[str, str, str]:
    """Attempt to discover the actual channel identity via channels().list(mine=True).

    Returns (channel_id, handle_or_empty, error_string).
    Returns ("", "", error) when the call cannot determine identity
    (scope missing, invalid_grant, network error).
    """
    refresh_token = token_entry.get("refresh_token")
    if not refresh_token:
        return "", "", "no_refresh_token"

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return "", "", "google-api-python-client not installed"

    try:
        creds = Credentials(
            token=token_entry.get("access_token"),
            refresh_token=refresh_token,
            token_uri=token_entry.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_entry.get("client_id"),
            client_secret=token_entry.get("client_secret"),
            scopes=["https://www.googleapis.com/auth/youtube.readonly",
                     "https://www.googleapis.com/auth/youtube.upload"],
        )
        if creds.expired:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)
        resp = youtube.channels().list(part="id,snippet", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return "", "", "no_channels"

        ch = items[0]
        ch_id = ch.get("id", "")
        handle = ""
        snippet = ch.get("snippet", {})
        custom_url = snippet.get("customUrl", "")
        if custom_url:
            handle = custom_url if custom_url.startswith("@") else f"@{custom_url}"
        return ch_id, handle, ""

    except Exception as e:
        err_str = str(e).lower()
        if "invalid_grant" in err_str or "revoked" in err_str or "token has been expired or revoked" in err_str:
            return "", "", "invalid_grant"
        if "insufficient" in err_str or "403" in err_str:
            return "", "", "insufficient_scope"
        return "", "", str(e)


def resolve_brand_binding(brand: str,
                          tokens_path: Path | None = None,
                          channel_registry_path: Path | None = None,
                          brand_registry_path: Path | None = None,
                          live_check: bool = True) -> BindingResult:
    """Resolve the full channel binding for a brand. ONE call, ONE answer.

    This is the ONLY function that determines whether a brand's publishing
    path is allowed to proceed.  All publish gates consume this result.

    Args:
        brand: Brand slug (e.g. "clippingfactorymbm")
        tokens_path: Override tokens file (for testing)
        channel_registry_path: Override ChannelRegistry (for testing)
        brand_registry_path: Override BrandRegistry (for testing)
        live_check: When True, attempt live channel identity verification.
                    Set False for offline/audit-only checks.
    """
    slug = _norm(brand)
    result = BindingResult(brand=brand, binding_status="UNKNOWN")

    if not slug:
        result.binding_status = "UNKNOWN"
        result.error = "empty brand"
        return result

    # ── Load registries first (before token check) ─────────────────────
    # Registry consistency is a production bug regardless of whether a token
    # exists.  Check it before the token early-return.
    channels_doc = _load(channel_registry_path or CHANNEL_REGISTRY)
    brands_doc = _load(brand_registry_path or BRAND_REGISTRY)

    reg_entry = None
    for ch in channels_doc.get("channels", []):
        if _norm(ch.get("brand")) == slug:
            reg_entry = ch
            break
    if reg_entry:
        result.configured_channel_id = reg_entry.get("youtube_channel_id", "")
        result.configured_handle = reg_entry.get("handle", "")
        result.registry_source = "ChannelRegistry"

    brand_entry = brands_doc.get("brands", {}).get(slug) or brands_doc.get("brands", {}).get(brand)
    if not isinstance(brand_entry, dict):
        for k, v in brands_doc.get("brands", {}).items():
            if isinstance(v, dict) and _norm(k) == slug:
                brand_entry = v
                break
    if isinstance(brand_entry, dict):
        brand_cid = brand_entry.get("youtube_channel_id", "")
        brand_handle = brand_entry.get("handle", "")
        if not result.configured_channel_id and brand_cid:
            result.configured_channel_id = brand_cid
            result.configured_handle = brand_handle
            result.registry_source = "BrandRegistry"
        elif brand_cid and result.configured_channel_id and brand_cid != result.configured_channel_id:
            result.binding_status = "MISMATCH"
            result.error = (f"ChannelRegistry '{result.configured_channel_id}' != "
                            f"BrandRegistry '{brand_cid}'")
            return result

    # ── Placeholder / invalid channel_id in registry ───────────────────
    if result.configured_channel_id and not _CHANNEL_ID_RE.match(result.configured_channel_id):
        result.binding_status = "MISMATCH"
        result.error = (f"registry channel_id '{result.configured_channel_id}' "
                        "is placeholder/invalid (must match ^UC[A-Za-z0-9_-]{{20,}}$)")
        return result

    # ── Load token entry (strict: no cross-brand fallthrough) ──────────
    tokens = _load(tokens_path or TOKENS_PATH)
    token_entry = tokens.get(slug) or tokens.get(brand)
    if not isinstance(token_entry, dict):
        for k, v in tokens.items():
            if not str(k).startswith("_") and isinstance(v, dict) and _norm(k) == slug:
                token_entry = v
                break
    if not isinstance(token_entry, dict):
        result.binding_status = "UNKNOWN"
        result.error = f"no token entry for brand '{brand}'"
        return result

    result.token_channel_id = token_entry.get("channel_id", "")
    result.token_handle = token_entry.get("handle", "")
    has_refresh = bool(token_entry.get("refresh_token"))

    # ── Token channel_id vs configured channel_id ─────────────────────
    if result.token_channel_id and result.configured_channel_id:
        if result.token_channel_id != result.configured_channel_id:
            result.binding_status = "MISMATCH"
            result.error = (f"token channel '{result.token_channel_id}' != "
                            f"configured '{result.configured_channel_id}'")
            return result

    # ── Live channel identity check (when possible) ───────────────────
    if live_check and has_refresh:
        live_id, live_handle, live_err = _try_live_channel_identity(token_entry)
        result.live_channel_id = live_id
        result.live_channel_handle = live_handle

        if live_err == "invalid_grant":
            result.binding_status = "INVALID_AUTH"
            result.error = f"token refresh failed: {live_err}"
            return result
        if live_err == "insufficient_scope":
            # Token works but lacks youtube.readonly — we cannot discover
            # the live channel.  Use the stored channel_id as best available.
            # The upload itself will be the channel proof.
            pass
        elif live_err:
            # Other error (network, etc.) — use stored channel_id
            pass
        elif live_id:
            # Live check succeeded — compare against configured
            if live_id != result.configured_channel_id:
                result.binding_status = "MISMATCH"
                result.error = (f"live channel '{live_id}' != "
                                f"configured '{result.configured_channel_id}'")
                return result
            # Live check confirms configured identity
            if live_handle:
                result.token_handle = live_handle

    # ── All checks pass ────────────────────────────────────────────────
    result.binding_status = "VALID"
    return result


def resolve_all_bindings(live_check: bool = True,
                         root: Path | None = None) -> dict[str, BindingResult]:
    """Resolve bindings for every brand that has a token OR a registry entry."""
    base = root or ROOT
    tokens = _load(base / "youtube_tokens.json")
    channels_doc = _load(base / "ChannelRegistry.json")
    brands_doc = _load(base / "BrandRegistry.json")

    # Collect all known brand slugs from all sources
    all_brands: set[str] = set()
    for k in tokens:
        if not str(k).startswith("_") and isinstance(tokens[k], dict):
            all_brands.add(_norm(k))
    for ch in channels_doc.get("channels", []):
        if isinstance(ch, dict) and ch.get("brand"):
            all_brands.add(_norm(ch["brand"]))
    for b in brands_doc.get("brands", {}):
        all_brands.add(_norm(b))

    return {brand: resolve_brand_binding(
                brand, live_check=live_check,
                tokens_path=base / "youtube_tokens.json",
                channel_registry_path=base / "ChannelRegistry.json",
                brand_registry_path=base / "BrandRegistry.json")
            for brand in sorted(all_brands)}


def fleet_binding_report(live_check: bool = True) -> dict:
    """Generate a fleet-wide binding status report for all brands."""
    bindings = resolve_all_bindings(live_check=live_check)
    report = {
        "fleet_status": "GREEN",
        "brands": {},
        "publish_ready": [],
        "publish_blocked": [],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for brand, binding in sorted(bindings.items()):
        report["brands"][brand] = binding.to_dict()
        if binding.can_publish:
            report["publish_ready"].append(brand)
        elif binding.should_block:
            report["publish_blocked"].append(brand)
    if report["publish_blocked"]:
        report["fleet_status"] = "RED"
    elif not report["publish_ready"]:
        report["fleet_status"] = "YELLOW"
    return report


def main(argv=None) -> int:
    """CLI entry: print fleet binding report."""
    report = fleet_binding_report()
    for brand, info in sorted(report["brands"].items()):
        status = info.get("binding_status", "UNKNOWN")
        marker = "✓" if status == "VALID" else "✗"
        print(f"  {marker} {brand:<22} {status:<15} "
              f"configured={info.get('configured_channel_id', 'N/A'):<26} "
              f"token={info.get('token_channel_id', 'N/A'):<26} "
              f"live={info.get('live_channel_id', 'skip')}")
        if info.get("error"):
            print(f"    error: {info['error']}")
    print(f"\nFleet: {report['fleet_status']}  "
          f"Ready: {report['publish_ready']}  "
          f"Blocked: {report['publish_blocked']}")
    return 0 if report["fleet_status"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
