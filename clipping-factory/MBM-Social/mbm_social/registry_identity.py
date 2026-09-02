"""
registry_identity -- canonical brand/channel identity checks.

Canonical identity = the real, verified channel IDs stored in
youtube_tokens.json (written only by the OAuth consent flow). Registries must
match it exactly. Placeholder-style IDs ("UC_BrandName") are production bugs:
they make the API publisher refuse the upload and silently degrade to browser
automation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS_PATH = ROOT / "youtube_tokens.json"
CHANNEL_REGISTRY = ROOT / "ChannelRegistry.json"
BRAND_REGISTRY = ROOT / "BrandRegistry.json"

_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{20,}$")

AUTH_STATUS_LABELS = {
    "authenticated": "authenticated",
    "invalid_grant": "invalid_grant",
    "unknown": "unknown",
}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def token_channel_ids(tokens_path: Path | None = None) -> dict:
    data = _load(tokens_path or TOKENS_PATH)
    out = {}
    for brand, entry in data.items():
        if str(brand).startswith("_") or not isinstance(entry, dict):
            continue
        if entry.get("channel_id"):
            out[str(brand)] = entry["channel_id"]
    return out


def token_auth_status(brand: str, tokens_path: Path | None = None) -> str:
    """Best-effort auth label WITHOUT network calls or secret exposure.

    authenticated = refresh token present AND last_verified recorded by the
    OAuth tool. unknown otherwise (a live refresh probe is the only proof).
    """
    entry = (_load(tokens_path or TOKENS_PATH) or {}).get(brand)
    if not isinstance(entry, dict):
        return AUTH_STATUS_LABELS["unknown"]
    if entry.get("refresh_token") and entry.get("last_verified"):
        return AUTH_STATUS_LABELS["authenticated"]
    return AUTH_STATUS_LABELS["unknown"]


def check_registries(root: Path | None = None) -> dict:
    """Cross-check ChannelRegistry + BrandRegistry + tokens via brand_identity_resolver.

    This is a read-only audit.  For live binding verification (which attempts
    token refresh), use brand_identity_resolver.fleet_binding_report(live_check=True).
    """
    root = root or ROOT
    try:
        from mbm_social.brand_identity_resolver import resolve_all_bindings
        bindings = resolve_all_bindings(live_check=False, root=root)
        brands = {}
        issues = []
        for brand, binding in bindings.items():
            brands[brand] = {
                "platform": "youtube",
                "channel_id": binding.configured_channel_id,
                "channel_url": (f"https://www.youtube.com/channel/{binding.configured_channel_id}"
                                if _CHANNEL_ID_RE.match(binding.configured_channel_id) else ""),
                "auth_status": token_auth_status(brand, root / "youtube_tokens.json"),
                "binding_status": binding.binding_status,
            }
            if not _CHANNEL_ID_RE.match(binding.configured_channel_id):
                issues.append(f"{brand}: placeholder/invalid channel id '{binding.configured_channel_id}' in registry")
            elif binding.binding_status == "MISMATCH":
                issues.append(f"{brand}: {binding.error}")
        return {"ok": not issues, "issues": issues, "brands": brands,
                "canonical_source": "youtube_tokens.json",
                "resolver": "brand_identity_resolver"}
    except ImportError:
        # Fallback to legacy cross-check if resolver unavailable
        return _check_registries_legacy(root)


def _check_registries_legacy(root: Path) -> dict:
    """Legacy cross-check without the brand_identity_resolver."""
    canonical = token_channel_ids(root / "youtube_tokens.json")
    channels_doc = _load(root / "ChannelRegistry.json")
    brands_doc = _load(root / "BrandRegistry.json")
    issues = []
    brands = {}
    reg_channels = {c.get("brand"): c for c in channels_doc.get("channels", [])
                    if isinstance(c, dict)}
    for brand, chan in sorted(reg_channels.items()):
        cid = chan.get("youtube_channel_id", "")
        tok_id = canonical.get(brand, "")
        url = f"https://www.youtube.com/channel/{cid}" if _CHANNEL_ID_RE.match(cid) else ""
        brands[brand] = {"platform": "youtube",
                         "channel_id": cid,
                         "channel_url": url,
                         "auth_status": token_auth_status(brand, root / "youtube_tokens.json")}
        if not _CHANNEL_ID_RE.match(cid):
            issues.append(f"{brand}: placeholder/invalid channel id '{cid}' in ChannelRegistry")
        elif tok_id and tok_id != cid:
            issues.append(f"{brand}: ChannelRegistry '{cid}' != token channel '{tok_id}'")
        b = brands_doc.get("brands", {}).get(brand)
        if isinstance(b, dict) and b.get("youtube_channel_id") != cid:
            issues.append(f"{brand}: BrandRegistry '{b.get('youtube_channel_id')}' "
                          f"!= ChannelRegistry '{cid}'")
    for brand in canonical:
        if brand not in reg_channels:
            issues.append(f"{brand}: token exists but no ChannelRegistry entry")
    return {"ok": not issues, "issues": issues, "brands": brands,
            "canonical_source": "youtube_tokens.json"}


def main(argv=None) -> int:
    report = check_registries()
    for brand, info in report["brands"].items():
        print(f"{brand:<22} {info['platform']:<9} {info['channel_id']:<26} "
              f"auth={info['auth_status']}")
    for issue in report["issues"]:
        print(f"ISSUE: {issue}")
    print("registry_consistency:", "OK" if report["ok"] else "FAILED")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
