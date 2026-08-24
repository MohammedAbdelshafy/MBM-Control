"""
whop.py — Whop Revenue OS control CLI
======================================
Single entry point over the revenue subsystem. Read-only by default;
anything that sends/mutates goes through whop_governor.py levels.

Commands:
  status          account/API-health/snapshot truth (NO network; instant)
  sync            pull a fresh LIVE snapshot via whop_live (network)
  products        product intelligence table for the five live products
  revenue         canonical revenue summary + provenance
  funnel          funnel counts + conversion rates (+ per-product)
  customers       Customer 360 table
  opportunities   ranked revenue opportunities with evidence
  upsells         upsell candidates + matched real offers
  winbacks        churned/at-risk customers eligible for winback
  experiments     experiment registry status (INCONCLUSIVE until gated)
  alerts          at-risk memberships + system warnings
  economics       unit economics (UNAVAILABLE where evidence is missing)
  simulate        dry-run pipeline: ingest legacy analytics -> command center
  qa              run whop_revenue_qa.py
  command-center  full JSON command center payload

Usage: python MBM/Whop/whop.py <command>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import whop_revenue_os as ros  # noqa: E402


def _print(data):
    try:
        print(json.dumps(data, indent=2, default=str))
    except UnicodeEncodeError:
        print(json.dumps(data, default=str).encode("ascii", "replace").decode())


def cmd_status():
    """Instant truth panel: no network calls — reads the persisted snapshot."""
    import whop_live as wl
    import whop_product_intel as wpi
    snap = wl.load_previous_snapshot()
    members = wl.members_report(snap)
    revenue = wl.revenue_report(snap)
    health = wl.compute_sync_health()
    blockers = []
    if members["status"] != "VERIFIED":
        blockers.append({"blocker": "membership_data_unverified",
                         "detail": members.get("reason")})
    if health["health"] in ("FAILED", "STALE", "UNAVAILABLE"):
        blockers.append({"blocker": f"sync_health_{health['health']}",
                         "detail": health.get("reason")})
    cta = wpi.audit_ctas()
    if cta["dead"]:
        blockers.append({"blocker": "dead_ctas", "detail": f"{cta['dead']} dead CTA(s)"})
    if cta["live_products_without_cta"]:
        blockers.append({"blocker": "products_without_tracked_cta",
                         "detail": cta["live_products_without_cta"]})
    _print({
        "whop_account": snap.get("account_id") or "UNKNOWN",
        "api_health": health,
        "last_successful_sync": snap.get("last_successful_sync"),
        "last_attempt": snap.get("last_attempt"),
        "snapshot_status": wl.classify_staleness(snap),
        "membership_data_status": members,
        "revenue_data_status": revenue,
        "product_count": len(snap.get("products") or []),
        "critical_blockers": blockers or ["none"],
        "mode": ("PRE_REVENUE" if revenue["value"] == "UNAVAILABLE"
                 else "REVENUE_ACTIVE"),
        "next_revenue_objective": wpi.FIRST_REVENUE_OBJECTIVE["objective_id"],
    })


def cmd_sync():
    """Force a fresh live sync (the only network-touching command here)."""
    import whop_live as wl
    snap = wl.sync_live()
    members = wl.members_report(snap)
    revenue = wl.revenue_report(snap)
    health = wl.compute_sync_health()
    _print({
        "snapshot_status": snap.get("snapshot_status"),
        "account_id": snap.get("account_id"),
        "endpoints": {
            "products": len(snap.get("products") or []),
            "plans": len(snap.get("plans") or []),
            "memberships_verified": members["status"] == "VERIFIED",
        },
        "memberships_active": members["value"],
        "memberships_reason": members.get("reason"),
        "revenue": revenue,
        "errors": snap.get("errors"),
        "carry_forward_applied": snap.get("_carry_forward_applied"),
        "api_health": health,
    })


def cmd_products():
    """Product intelligence table for the five LIVE products."""
    import whop_product_intel as wpi
    snap = ros.REVENUE_REPORT
    _print({
        "inventory_source": wpi.intel_summary()["live_inventory_source"],
        "product_intel": wpi.PRODUCT_INTEL,
        "ladder": wpi.PRODUCT_LADDER,
        "positioning": wpi.POSITIONING,
        "recurring_analysis": wpi.RECURRING_ANALYSIS,
        "evidence": [str(snap)],
    })


def cmd_revenue():
    _print({"revenue": ros.revenue_summary(),
            "subscriptions": ros.subscriptions(),
            "economics": ros.unit_economics()})


def cmd_funnel():
    _print(ros.compute_funnel())


def cmd_customers():
    rows = []
    for c in ros.build_customer_360():
        nba = c.get("next_best_action") or {}
        rows.append({
            "customer_id": c["identity"]["customer_id"],
            "email": c["identity"].get("email"),
            "lifecycle_state": c["lifecycle_state"],
            "health_score": c["health_score"],
            "revenue_usd": c["revenue_usd"],
            "next_best_action": nba.get("action"),
            "why": nba.get("reason"),
            "governor_level": nba.get("governor_level"),
            "in_cooldown": nba.get("in_cooldown"),
        })
    _print({"customers": rows,
            "provenance": "REAL" if rows else "UNAVAILABLE",
            "evidence": [str(ros.MEMBERSHIPS_LEDGER), str(ros.EVENTS_FILE)]})


def cmd_opportunities():
    """Acquisition-first opportunity queue + evidence-backed engine output."""
    import whop_product_intel as wpi
    _print({"revenue_opportunity_queue": wpi.OPPORTUNITY_QUEUE,
            "first_revenue_objective": wpi.FIRST_REVENUE_OBJECTIVE,
            "engine_opportunities": ros.identify_revenue_opportunities(),
            "provenance": "DERIVED",
            "evidence": [str(ros.EVENTS_FILE), str(ros.MEMBERSHIPS_LEDGER)]})


def cmd_upsells():
    cat = ros.load_catalog()
    offers = ros.match_offer({"lifecycle_state": "UPSELL_READY"}, catalog=cat)
    buyers = [c for c in ros.build_customer_360() if c["revenue_usd"] > 0]
    _print({"upsell_candidates": [{"customer_id": c["identity"]["customer_id"],
                                   "revenue_usd": c["revenue_usd"],
                                   "state": c["upsell_state"]} for c in buyers],
            "ranked_offers": offers[:3],
            "provenance": "DERIVED",
            "evidence": cat["evidence"]})


def cmd_winbacks():
    rows = []
    for m in ros._memberships_latest():
        if m.get("stage") in ("churned", "at_risk"):
            rows.append({"membership_id": m.get("membership_id"),
                         "stage": m.get("stage"),
                         "reason": m.get("reason"),
                         "scanned_at": m.get("scanned_at")})
    _print({"winback_candidates": rows,
            "cooldown_days": ros.OUTREACH_COOLDOWN_DAYS,
            "max_attempts": ros.MAX_OUTREACH_ATTEMPTS,
            "provenance": "REAL" if rows else "UNAVAILABLE",
            "evidence": [str(ros.MEMBERSHIPS_LEDGER), str(ros.ENGAGE_LOG)]})


def cmd_experiments():
    reg_file = ros.DATA_DIR / "experiments.json"
    data = {}
    if reg_file.exists():
        try:
            data = json.loads(reg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    exps = []
    for eid, e in (data.get("experiments") or {}).items():
        la = e.get("last_analysis") or {}
        exps.append({"id": eid,
                     "decision": e.get("decision"),
                     "verdict": la.get("verdict", "NOT_ANALYZED"),
                     "sample_counts": e.get("sample_counts", {}),
                     "policy": la.get("decision_policy", "winner needs >=100 views/variant AND >=7d")})
    _print({"experiments": exps or "UNAVAILABLE (none registered)",
            "registry": str(reg_file)})


def cmd_alerts():
    alerts = []
    report = {}
    if ros.REVENUE_REPORT.exists():
        try:
            report = json.loads(ros.REVENUE_REPORT.read_text(encoding="utf-8"))
        except Exception:
            report = {}
    for err in report.get("errors", []):
        alerts.append({"severity": "high" if "not authorized" in err else "medium",
                       "source": "whop_revenue.json",
                       "message": err})
    for m in ros._memberships_latest():
        if m.get("stage") == "at_risk":
            alerts.append({"severity": "high", "source": "memberships_ledger",
                           "message": f"at_risk membership {m.get('membership_id')}: {m.get('reason')}"})
    cc = ros.command_center()
    for op in cc["opportunities"]:
        if op.get("priority", 0) >= 0.8:
            alerts.append({"severity": "medium", "source": "opportunity_engine",
                           "message": f"{op['type']} (count={op.get('count')})"})
    _print({"alerts": alerts or [], "provenance": "DERIVED"})


def cmd_economics():
    _print(ros.unit_economics())


def cmd_simulate():
    ingest = ros.ingest_legacy_analytics(dry_run=True)
    cc = ros.command_center()
    _print(_contract("success", {
        "dry_run_ingest_legacy_analytics": ingest,
        "funnel": cc["funnel"],
        "revenue": cc["revenue"],
        "opportunity_count": len(cc["opportunities"]),
    }, next_action="run 'whop.py simulate --apply' via ingest-analytics to commit"))


def cmd_qa():
    proc = subprocess.run([sys.executable, str(BASE_DIR / "whop_revenue_qa.py")],
                          capture_output=True, text=True, timeout=120)
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    return proc.returncode


def cmd_command_center():
    _print(ros.command_center())


def _classify_event(e: dict) -> str:
    """REAL / TEST / MOCK / UNKNOWN — smoke markers never become revenue."""
    eid = str(e.get("event_id") or "")
    if eid.startswith("smoke_"):
        return "TEST"
    uid = str((e.get("customer_ref") or {}).get("user_id") or "")
    meta = e.get("metadata") or {}
    if uid.startswith("usr_smoke") or (e.get("session_id") == "smoke_sess") \
            or (e.get("attribution") or {}).get("utm_source") == "smoke" \
            or e.get("source") == "smoke" or meta.get("utm_source") == "smoke":
        return "TEST"
    if not eid:
        return "UNKNOWN"
    return "REAL"


def cmd_daily():
    """Daily revenue command: traffic/clicks/checkouts/purchases/revenue/customers/
    top product/top source/funnel leak/next action. REAL evidence only;
    UNKNOWN stays UNKNOWN; TEST never counts as revenue."""
    events = []
    if ros.EVENTS_FILE.exists():
        for line in ros.EVENTS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def stage(name):
        rows = [e for e in events if e.get("event_name") == name]
        real = [e for e in rows if _classify_event(e) == "REAL"]
        return {"count": len(rows), "real": len(real), "test": len(rows) - len(real),
                "classification": ("REAL" if real else
                                   ("TEST" if rows else "NO_DATA"))}

    views, clicks, checkouts = stage("landing_view"), stage("cta_click"), stage("checkout_started")
    purchases = [e for e in events
                 if e.get("event_name") == "purchase" and _classify_event(e) == "REAL"
                 and e.get("source") == "whop_webhook"]
    revenue = sum(float(e.get("amount_usd") or 0) for e in purchases)
    customers = {json.dumps(e.get("customer_ref"), sort_keys=True): True for e in purchases}
    by_product, by_source = {}, {}
    for e in purchases:
        pid = (e.get("metadata") or {}).get("product_id") or "UNATTRIBUTED"
        by_product[pid] = by_product.get(pid, 0) + 1
    for e in events:
        src = (e.get("attribution") or {}).get("utm_source") \
            or (e.get("metadata") or {}).get("utm_source")
        if src and _classify_event(e) == "REAL":
            by_source[src] = by_source.get(src, 0) + 1

    # Section-11 leak classification on REAL stages only.
    leak, next_action = "NO_DATA", "execute whop_audit_day1 touches"
    r_v, r_c = views["real"], clicks["real"]
    if purchases:
        ful_log = BASE_DIR / "logs" / "fulfillments.jsonl"
        fulfilled = ful_log.exists() and ful_log.stat().st_size > 0
        leak = None if fulfilled else "PURCHASE_NO_FULFILLMENT -> operations: run REVENUE_AUDIT_FULFILLMENT_SOP"
        next_action = "upsell qualification per SOP" if fulfilled else "fulfill within 72h clock"
    elif checkouts["real"] > 0:
        leak = "CHECKOUT_NO_PURCHASE -> trust/pricing/checkout problem"
        next_action = "inspect checkout drop-off; do NOT write software"
    elif r_c > 0:
        leak = "CTA_NO_CHECKOUT -> landing/offer problem" if checkouts["count"] == 0 \
            else "CHECKOUT_STARTED_UNVERIFIED -> verify beacon wiring"
        next_action = "fix landing offer clarity before more traffic"
    elif r_v > 0:
        leak = "TRAFFIC_NO_CTA -> messaging problem"
        next_action = "strengthen CTA copy; keep traffic constant"
    elif views["count"] > 0 or clicks["count"] > 0:
        leak = "ONLY_TEST_TRAFFIC -> no real distribution yet"
    else:
        leak = "NO_TRAFFIC -> distribution problem"

    import whop_live as wl
    snap = wl.load_previous_snapshot()
    members = wl.members_report(snap)
    _print({
        "date": _now_iso_day(),
        "traffic": views, "clicks": clicks, "checkouts": checkouts,
        "purchases": {"count": len(purchases), "classification": ("REAL" if purchases else "NO_DATA")},
        "revenue": ({"value": revenue, "currency": "USD", "classification": "REAL"}
                    if purchases else
                    {"value": "UNAVAILABLE", "reason": "NO_REVENUE_EVIDENCE"}),
        "customers": {"count": len(customers),
                      "classification": ("REAL" if customers else "NO_DATA")},
        "top_product": (max(by_product, key=by_product.get) if by_product else "UNAVAILABLE"),
        "top_source": (max(by_source, key=by_source.get) if by_source else "UNAVAILABLE"),
        "funnel_leak": leak,
        "next_action": next_action,
        "memberships_active": members["value"],
        "membership_status": members["status"],
        "provenance": {"events_file": str(ros.EVENTS_FILE)},
    })


def _now_iso_day() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


COMMANDS = {
    "status": cmd_status, "sync": cmd_sync, "products": cmd_products,
    "revenue": cmd_revenue, "funnel": cmd_funnel,
    "customers": cmd_customers, "opportunities": cmd_opportunities,
    "upsells": cmd_upsells, "winbacks": cmd_winbacks,
    "experiments": cmd_experiments, "alerts": cmd_alerts,
    "economics": cmd_economics, "simulate": cmd_simulate, "qa": cmd_qa,
    "daily": cmd_daily, "command-center": cmd_command_center,
}


def _contract(status, outputs, next_action="continue", owner="system"):
    return {"status": status, "inputs": {}, "outputs": outputs, "errors": [],
            "next_action": next_action, "owner": owner}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command '{cmd}'. Use one of: {', '.join(COMMANDS)}")
        sys.exit(1)
