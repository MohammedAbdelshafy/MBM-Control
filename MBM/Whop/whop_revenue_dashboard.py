"""
whop_revenue_dashboard.py — Revenue Command Center (terminal)
==============================================================
Renders ONLY evidence-backed data with explicit provenance labels:

    [REAL]        read from a live-system artifact
    [DERIVED]     computed deterministically from REAL inputs
    [UNAVAILABLE] no evidence exists yet (never guessed, never mocked)

Sources:
- MBM/Whop/logs/revenue_events.jsonl   canonical store (webhooks + landing)
- MBM/Whop/logs/analytics_log.json     landing beacon events (legacy array)
- MBM/Whop/logs/whop_memberships.json  membership scan ledger
- MBM/Whop/logs/whop_engage_log.json   lifecycle engagement state
- MBM/Whop/logs/whop_revenue.json      last live Whop API report
- MBM/Whop/data/experiments.json       experiment registry
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import whop_revenue_os as ros  # noqa: E402


def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def render_dashboard():
    print("=" * 64)
    print(" WHOP REVENUE COMMAND CENTER  (evidence-labelled)")
    print("=" * 64)

    # ── 0. Zero-revenue / PRE-REVENUE mode banner (Phase 12) ────
    import whop_live as wl
    snap = wl.load_previous_snapshot()
    members_r = wl.members_report(snap)
    revenue_r = wl.revenue_report(snap)
    health = wl.compute_sync_health()
    pre_revenue = revenue_r["value"] == "UNAVAILABLE"
    if pre_revenue:
        print("\n[ LIVE REVENUE STATUS ]                  source: REAL/UNAVAILABLE")
        print(f"  Verified Revenue:   {revenue_r['value']}")
        print(f"  Verified Members:   {members_r['value']}"
              + (f" ({members_r.get('reason')})" if members_r.get("reason") else ""))
        print(f"  Products:           {len(snap.get('products') or [])}")
        print(f"  API Health:         {health['health']} - {health.get('reason')}")
        if members_r["status"] != "VERIFIED":
            print(f"  Primary Blocker:    Membership data unverified")
        else:
            print(f"  Primary Blocker:    No verified purchase yet")
        print("  Next Objective:     FIRST VERIFIED PURCHASE")

    # ── 1. Live account snapshot ────────────────────────────────
    print("\n[ LIVE WHOP ACCOUNT ]                    source: REAL")
    report = _load_json(LOGS_DIR / "whop_revenue.json", {})
    if report.get("account_id"):
        print(f"  Account:          {report['account_id']} "
              f"(mode={report.get('mode', 'n/a')}, "
              f"state={report.get('snapshot_status', 'n/a')})")
        products = report.get("products") or []
        plans_by_product = {}
        for pl in report.get("plans") or []:
            plans_by_product.setdefault(pl.get("product_id"), []).append(pl)
        print(f"  Products live:    {len(products)}")
        for p in products[:8]:
            price_bits = []
            for pl in plans_by_product.get(p.get("id"), []) or p.get("plans") or []:
                price = pl.get("initial_price_usd") or pl.get("initial_price")
                per = "/mo" if (pl.get("plan_type") == "renewal") else ""
                if isinstance(price, (int, float)):
                    price_bits.append(f"${price:g}{per}")
            prices = f" [{'/'.join(price_bits)}]" if price_bits else ""
            members_txt = (f"  members={p['member_count']}"
                           if p.get("member_count") is not None else "")
            print(f"    - {p.get('title')}{members_txt}{prices}")
        mem_status = members_r["status"]
        print(f"  Active members:   {members_r['value']}"
              + ("" if mem_status == "VERIFIED" and isinstance(members_r['value'], int)
                 else f"  [{mem_status}]"))
        print(f"  Sync health:      {health['health']} | last ok: "
              f"{report.get('last_successful_sync') or 'never'}")
        if report.get("errors"):
            print(f"  API errors:       {len(report['errors'])} (see logs/whop_revenue.json)")
    else:
        print("  UNAVAILABLE - run `python MBM/Whop/whop.py sync` to pull a live snapshot")

    # ── 2. Subscription health ──────────────────────────────────
    print("\n[ SUBSCRIPTION HEALTH ]                  source: REAL")
    memberships = ros._memberships_latest()
    if memberships:
        stages = Counter(m.get("stage") or "unknown" for m in memberships)
        print(f"  Tracked unique memberships: {len(memberships)}")
        for stage, count in stages.most_common():
            print(f"    {stage:<10} {count}")
    else:
        print("  UNAVAILABLE - no membership scans yet (run whop_monetize.py monitor)")

    # ── 3. Revenue & funnel ─────────────────────────────────────
    print("\n[ REVENUE + FUNNEL ]                     source: DERIVED")
    rev = ros.revenue_summary()
    sub = ros.subscriptions()
    fun = ros.compute_funnel()
    if rev["orders"]:
        print(f"  Gross revenue:    ${rev['gross_revenue_usd']:,.2f}")
        print(f"  Orders:           {rev['orders']}   AOV: ${rev['aov_usd']}")
        print(f"  Refunds:          ${rev['refunds_usd']:,.2f}")
    else:
        print("  Purchases: none recorded")
    c = fun["counts"]
    print(f"  Funnel: views={c['landing_view']} clicks={c['cta_click']} signups={c['signup']} "
          f"checkouts={c['checkout_started']} purchases={c['purchase']}")
    if fun["overall_view_to_purchase"] is not None:
        print(f"  View->purchase conversion: {fun['overall_view_to_purchase']:.1%}")
    if not any(c.values()):
        print("  UNAVAILABLE - run ingest-analytics or wait for landing traffic")

    # ── 4. Experiments ──────────────────────────────────────────
    print("\n[ EXPERIMENTS ]                          source: DERIVED (gated)")
    reg = _load_json(DATA_DIR / "experiments.json", {})
    exps = reg.get("experiments") or {}
    if not exps:
        legacy = _load_json(LOGS_DIR / "analytics_log.json", [])
        variants = Counter(str(e.get("landing_variant")) for e in legacy
                           if e.get("event") == "landing_view")
        if variants:
            print("  headline_test_v1 (client-side split detected):")
            for v, n in sorted(variants.items()):
                print(f"    variant {v}: {n} views  [sample too small - verdict INCONCLUSIVE]")
        else:
            print("  No experiments registered. Register via whop_experiments.py create.")
    else:
        import whop_experiments as wexp
        for eid in exps:
            res = wexp.analyze_experiment(eid)
            print(f"  {eid}: verdict={res['verdict']}")
            for v, r in res["results_by_variant"].items():
                rate = f"{r['rate']:.1%}" if r["rate"] is not None else "n/a"
                print(f"    {v}: views={r['views']} conversions={r['conversions']} rate={rate}")

    # ── 5. Lifecycle engagement ─────────────────────────────────
    print("\n[ LIFECYCLE ENGAGEMENT ]                 source: REAL")
    engage = _load_json(LOGS_DIR / "whop_engage_log.json", {})
    actions = engage.get("actions_summary") or {}
    if any(actions.values()) or engage.get("updated_at"):
        print(f"  Updated:              {engage.get('updated_at', 'n/a')}")
        print(f"  Welcome emails:       {actions.get('welcome', 0)}")
        print(f"  Retention discounts:  {actions.get('retention_discount', 0)}")
        print(f"  Reactivation offers:  {actions.get('reactivation', 0)}")
    else:
        print("  UNAVAILABLE - engage bot has not acted on any member yet")

    # ── 6. Opportunities ────────────────────────────────────────
    print("\n[ TOP OPPORTUNITIES ]                    source: DERIVED")
    ops = ros.identify_revenue_opportunities()
    if ops:
        for op in ops[:5]:
            value = op.get("estimated_value") or op.get("estimated_value_modelled") or "?"
            tag = "" if str(value).startswith("$") is False else ""
            label = value if isinstance(value, str) else f"${value}"
            print(f"  [{op['priority']:.2f}] {op['type']} (n={op.get('count', '?')}) "
                  f"value={label} -> {op['recommended_action'][:70]}")
    else:
        print("  None identified yet (insufficient data)")

    # ── 7. Economics ────────────────────────────────────────────
    print("\n[ UNIT ECONOMICS ]                       source: DERIVED/UNAVAILABLE")
    eco = ros.unit_economics()
    print(f"  Net revenue: ${eco['net_revenue_usd']}" if eco["net_revenue_usd"] is not None
          else "  Net revenue: UNAVAILABLE (no orders)")
    for k in ("fulfillment_cost_usd", "ltv_usd", "cac_usd", "payback_days"):
        v = eco[k]
        print(f"  {k}: {'UNAVAILABLE' if v == 'UNAVAILABLE' else v}")

    print("\n" + "=" * 64)
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue": rev,
        "funnel": fun,
        "subscriptions": sub,
        "economics": eco,
    }


if __name__ == "__main__":
    result = render_dashboard()
    print(json.dumps({"status": result["status"], "mrr_provenance": "see subscriptions"}))
