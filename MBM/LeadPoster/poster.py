"""
MBM LeadPoster — post MBM real-estate leads to a pay-per-lead marketplace.

Design mirrors the clipping-platform flow:
  * Site posting mechanics live in sites/<site>.yaml (config only — no code
    changes to add a new marketplace).
  * Authentication uses a saved Playwright session (manual/form login), captured
    by export_marketplace_session.py, never hardcoded credentials.
  * DRY-RUN by default: validates field mapping and counts leads without
    touching the browser. Pass --post to actually submit.

Leads are read from the latest MBM LeadPacks CSV. A ledger (posted.json)
prevents re-posting the same lead.

Usage:
    python poster.py                 # dry-run: map + count only
    python poster.py --post          # actually submit (needs a session)
    python poster.py --site realestate_leadmarket --pack 2026-07-07
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MBM_ROOT = ROOT.parent
LEADPACKS = MBM_ROOT / "LeadPacks"
SESSIONS = ROOT / "sessions"
LEDGER = ROOT / "posted.json"


def _latest_pack() -> Path | None:
    if not LEADPACKS.exists():
        return None
    packs = sorted([p for p in LEADPACKS.iterdir() if p.is_dir()],
                   key=lambda p: p.name, reverse=True)
    for pack in packs:
        for name in ("FULL_PACK_*.csv", "WHOLESALERS_*.csv"):
            hits = sorted(pack.glob(name), reverse=True)
            if hits:
                return hits[0]
    return None


def load_leads(pack: str | None = None) -> list[dict]:
    if pack:
        path = LEADPACKS / f"Pack_{pack}" / f"WHOLESALERS_{pack}.csv"
        if not path.exists():
            path = LEADPACKS / f"Pack_{pack}" / f"FULL_PACK_{pack}.csv"
    else:
        path = _latest_pack()
    if not path or not path.exists():
        raise FileNotFoundError(f"No lead pack found (looked in {LEADPACKS})")
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[leads] loaded {len(rows)} rows from {path.name}")
    return rows


def load_site(site: str) -> dict:
    cfg = (ROOT / "sites" / f"{site}.yaml").read_text(encoding="utf-8")
    import yaml
    data = yaml.safe_load(cfg)
    # Normalize: site meta may live under a `site:` block or at top level.
    meta = data.get("site", {}) if isinstance(data.get("site"), dict) else {}
    meta = {**meta, **{k: v for k, v in data.items() if k not in ("site", "field_map")}}
    data["_meta"] = meta
    return data


def _session_for(site: str) -> str:
    # env override then session file (same pattern as clipping platforms)
    import os
    env = os.environ.get(f"{site.upper().replace('-', '_')}_SESSION_STATE")
    if env:
        return env
    fp = SESSIONS / f"{site}.json"
    if fp.exists():
        return fp.read_text(encoding="utf-8")
    return ""


def _ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"posted": []}


def _save_ledger(data: dict):
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def map_lead(lead: dict, field_map: dict) -> dict:
    """Map a CSV lead row -> {selector: value} using the site field_map."""
    out = {}
    for csv_col, selector in field_map.items():
        val = (lead.get(csv_col) or "").strip()
        if val:
            out[selector] = val
    return out


# Keywords that push a lead toward a specific buyer lane.
_DISTRESS_KW = ["probate", "foreclosure", "vacant", "pre-foreclosure", "eviction",
                "tired landlord", "high-equity", "absentee", "distressed", "motivated"]
_LEGAL_KW = ["probate", "eviction", "foreclosure defense", "debt", "personal injury"]
_HOME_KW = ["roof", "solar", "hvac", "foundation", "plumbing", "remodel", "repair", "urgent"]


def _signals(lead: dict, mapped: dict) -> dict:
    notes = (lead.get("Notes") or "").lower()
    distress = (lead.get("Distress_Signal") or "").strip() != ""
    distress = distress or any(k in notes for k in _DISTRESS_KW)
    try:
        conf = int(float(lead.get("Confidence") or 0))
    except (ValueError, TypeError):
        conf = 0
    return {
        "verified_contact": bool((lead.get("Phone") or "").strip() or (lead.get("Email") or "").strip()),
        "confidence_ge_60": conf >= 60,
        "property_signal": bool((lead.get("Property_Address") or "").strip()
                                or (lead.get("City") or "").strip()
                                or (lead.get("State") or "").strip()),
        "distress_or_intent": distress,
        "any_mappable_field": bool(mapped),
    }


def tier_for_lead(lead: dict, buyers_cfg: dict, field_map: dict) -> dict:
    """Score a lead into a price tier + recommended buyer lane."""
    mapped = map_lead(lead, field_map)
    sig = _signals(lead, mapped)
    tiers = buyers_cfg.get("tiers", {})
    chosen = "base"
    # Ascending order, no break: each matching tier overwrites the previous,
    # so the loop ends on the highest qualifying tier.
    for name in ("base", "mid", "premium"):
        reqs = tiers.get(name, {}).get("requires", [])
        if all(sig.get(r, False) for r in reqs):
            chosen = name
    price = tiers.get(chosen, {}).get("price_usd", 70)

    notes = (lead.get("Notes") or "").lower()
    if any(k in notes for k in _LEGAL_KW):
        lane = "legal"
    elif any(k in notes for k in _HOME_KW):
        lane = "home_services"
    else:
        lane = "investors_and_wholesalers"
    return {"tier": chosen, "price_usd": price, "buyer_lane": lane, "signals": sig}


def tier_report(leads: list[dict], buyers_cfg: dict, field_map: dict) -> dict:
    from collections import Counter
    tiers = Counter()
    lanes = Counter()
    value = 0
    for lead in leads:
        t = tier_for_lead(lead, buyers_cfg, field_map)
        tiers[t["tier"]] += 1
        lanes[t["buyer_lane"]] += 1
        value += t["price_usd"]
    return {"tiers": dict(tiers), "lanes": dict(lanes),
            "est_value_usd": value, "leads": len(leads)}


def run_dry(leads: list[dict], site_cfg: dict):
    fm = site_cfg.get("field_map", {})
    meta = site_cfg.get("_meta", {})
    print(f"\n[DRY-RUN] site='{meta.get('name')}'  post_url={meta.get('post_url')}")
    print(f"[DRY-RUN] field_map ({len(fm)} fields):")
    for col, sel in fm.items():
        print(f"    {col:16} -> {sel}")
    ready = 0
    for lead in leads:
        if map_lead(lead, fm):
            ready += 1
    print(f"[DRY-RUN] {ready}/{len(leads)} leads have at least one mappable field.")

    buyers = load_buyers()
    if buyers:
        rep = tier_report(leads, buyers, fm)
        print("\n[TIERS] pricing-ladder distribution (per lead strategy):")
        for t in ("premium", "mid", "base"):
            c = rep["tiers"].get(t, 0)
            price = buyers.get("tiers", {}).get(t, {}).get("price_usd", "?")
            print(f"    {t:8} (${price}): {c} leads")
        print("[TIERS] buyer-lane routing:")
        for lane, c in sorted(rep["lanes"].items(), key=lambda x: -x[1]):
            print(f"    {lane:28} {c} leads")
        print(f"[TIERS] estimated inventory value if all sold: ${rep['est_value_usd']:,}")

    print("[DRY-RUN] No browser used. Re-run with --post to submit (needs a session).")


def load_buyers() -> dict:
    bp = ROOT / "buyers.yaml"
    if not bp.exists():
        return {}
    import yaml
    return yaml.safe_load(bp.read_text(encoding="utf-8"))


def run_post(leads: list[dict], site: str, site_cfg: dict):
    session = _session_for(site)
    if not session:
        print(f"[POST] ERROR: no session for '{site}'. Run export_marketplace_session.py first.")
        sys.exit(1)
    from playwright.sync_api import sync_playwright

    fm = site_cfg.get("field_map", {})
    meta = site_cfg.get("_meta", {})
    post_url = meta.get("post_url")
    submit = site_cfg.get("submit_selector")
    success = site_cfg.get("success_selector")
    ledger = _ledger()
    posted_keys = set(ledger["posted"])
    buyers = load_buyers()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(storage_state=json.loads(session))
        page = ctx.new_page()
        count = 0
        for lead in leads:
            key = (lead.get("Company") or lead.get("Email") or str(lead))[:80]
            if key in posted_keys:
                print(f"[skip] already posted: {key}")
                continue
            mapped = map_lead(lead, fm)
            if not mapped:
                print(f"[skip] no mappable fields: {key}")
                continue
            tier = tier_for_lead(lead, buyers, fm) if buyers else {"tier": "base", "price_usd": 70, "buyer_lane": "investors_and_wholesalers"}
            try:
                page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                for sel, val in mapped.items():
                    el = page.query_selector(sel)
                    if el:
                        el.fill(val)
                btn = page.query_selector(submit)
                if not btn:
                    print(f"[FAIL] submit not found for {key}")
                    continue
                btn.click()
                page.wait_for_timeout(4000)
                ok = bool(page.query_selector(success)) if success else True
                ledger["posted"].append({
                    "key": key, "site": site,
                    "tier": tier["tier"], "price_usd": tier["price_usd"],
                    "buyer_lane": tier["buyer_lane"],
                    "at": datetime.now().isoformat(),
                    "status": "posted" if ok else "submitted_unconfirmed",
                })
                count += 1
                print(f"[{'OK' if ok else '??'}] posted {key}")
            except Exception as exc:
                print(f"[ERR] {key}: {exc}")
        _save_ledger(ledger)
        browser.close()
    print(f"[POST] done. Submitted {count} lead(s). Ledger -> {LEDGER}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="realestate_leadmarket")
    ap.add_argument("--pack", default=None, help="Pack date YYYY-MM-DD")
    ap.add_argument("--post", action="store_true", help="actually submit (else dry-run)")
    args = ap.parse_args()

    leads = load_leads(args.pack)
    site_cfg = load_site(args.site)
    if args.post:
        run_post(leads, args.site, site_cfg)
    else:
        run_dry(leads, site_cfg)


if __name__ == "__main__":
    main()
