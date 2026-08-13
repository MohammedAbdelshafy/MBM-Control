"""
verify_channels -- read the REAL channel id from each logged-in brand profile
and report + optionally patch BrandRegistry.json / ChannelRegistry.json.

YouTube Studio exposes the signed-in channel id at window.ytcfg 'CHANNEL_ID'.
We open each profile headless with the same anti-flag flags the publisher
uses, read those values, and print a table so the placeholder UC_* ids can be
replaced with truth.

Usage:
  python -m mbm_social.verify_channels            # report only
  python -m mbm_social.verify_channels --apply    # patch BrandRegistry + ChannelRegistry
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BRANDS = ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]

CHANNEL_ID_KEYS = ["CHANNEL_ID", "CHANNEL_ID_DELEGATED", "LOGGED_IN_USER_ID", "DELEGATED_SESSION_ID"]

_YT_CFG_EVAL = (
    "() => { const o = {}; if (window.ytcfg && ytcfg.get) {"
    " ['CHANNEL_ID','CHANNEL_ID_DELEGATED','CHANNEL','CHANNEL_NAME','CHANNEL_HANDLE',"
    "  'DELEGATED_SESSION_ID','LOGGED_IN_USER_ID','VISITOR_DATA'].forEach(k => {"
    "   try { const v = ytcfg.get(k); if (v) o[k] = v; } catch(e){} }); }"
    " const el = document.querySelector('ytcp-branding') || document.querySelector('ytcp-text#branding');"
    " if (el) o.branding = el.textContent.trim(); return o; }"
)


def _profile_dir(brand: str) -> Path:
    return ROOT / f"youtube_profile_{brand}"


def probe_brand(brand: str) -> dict:
    """Headless read of the signed-in channel id from the brand profile."""
    meta = {"brand": brand, "channel_id": None, "handler_name": None, "ok": False}
    if sync_playwright is None:
        meta["note"] = "playwright missing"
        return meta
    profile = _profile_dir(brand)
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            page = ctx.new_page()
            page.goto("https://studio.youtube.com/channel/UC", timeout=45000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            time.sleep(3)
            if "accounts.google.com" in page.url:
                meta["note"] = "login required"
                ctx.close()
                return meta
            payload = page.evaluate(_YT_CFG_EVAL)
            meta["ytcfg"] = payload
            cid = None
            for k in CHANNEL_ID_KEYS:
                v = payload.get(k)
                if v and str(v).startswith("UC"):
                    cid = v
                    break
            meta["channel_id"] = cid
            meta["handler_name"] = payload.get("CHANNEL_NAME") or payload.get("CHANNEL_HANDLE")
            meta["ok"] = bool(cid)
            ctx.close()
    except Exception as e:
        meta["error"] = str(e)
    return meta


def report_all(apply: bool = False) -> None:
    results = []
    for brand in BRANDS:
        m = probe_brand(brand)
        results.append(m)
        print(f"[{m['brand']}] channel_id={m.get('channel_id')} ok={m.get('ok')} "
              f"{m.get('note', '')} {m.get('handler_name', '')}")
    if apply:
        _apply(results)
    else:
        print("\n--report only-- Use --apply to update registries.")


def _apply(results) -> None:
    registry_path = ROOT / "BrandRegistry.json"
    channel_path = ROOT / "ChannelRegistry.json"
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    chanreg = json.loads(channel_path.read_text(encoding="utf-8"))

    changed = 0
    for m in results:
        brand = m.get("brand")
        cid = m.get("channel_id")
        if not brand or not cid:
            continue
        if brand in reg.get("brands", {}):
            prev = reg["brands"][brand].get("youtube_channel_id")
            if prev != cid:
                reg["brands"][brand]["youtube_channel_id"] = cid
                changed += 1
                print(f"[UPGRADE] BrandRegistry[{brand}] {prev} -> {cid}")
        for ch in chanreg.get("channels", []):
            if ch.get("brand") == brand:
                prev = ch.get("youtube_channel_id")
                if prev != cid:
                    ch["youtube_channel_id"] = cid
                    changed += 1
                    print(f"[UPGRADE] ChannelRegistry[{brand}] {prev} -> {cid}")

    reg["updated"] = "2026-08-08"
    chanreg["updated"] = "2026-08-08"
    registry_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    channel_path.write_text(json.dumps(chanreg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[apply] updated {changed} channel id(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Patch the registries with the real channel ids.")
    args = parser.parse_args()
    report_all(apply=args.apply)