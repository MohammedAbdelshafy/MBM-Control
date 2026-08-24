import json
import os
import sys
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

def run_qa():
    score = 100
    report = []
    
    def log(test, status, msg=""):
        report.append(f"{test}: {status} {('- ' + msg) if msg else ''}")
        return status == "PASS"

    # 1. Landing Page
    landing_path = REPO_ROOT / "public" / "productized-service" / "ai-consultancy-sprint" / "landing.html"
    if landing_path.exists():
        content = landing_path.read_text(encoding="utf-8")
        if "/api/analytics/track" in content:
            log("Landing page CTA routing", "PASS")
        else:
            log("Landing page CTA routing", "FAIL", "No analytics tracked")
            score -= 10
    else:
        log("Landing page", "FAIL", "Missing landing.html")
        score -= 15

    # 2. Pricing Consistency
    spec_path = BASE_DIR / "ai-consultancy-agency" / "whop_product_spec.json"
    if spec_path.exists():
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            plans = spec.get("plans", [])
            # Simple check if prices exist
            if any(p.get("initial_price") == 297 for p in plans) and any(p.get("initial_price") == 1497 for p in plans):
                log("Pricing consistency", "PASS")
            else:
                log("Pricing consistency", "FAIL", "Missing standard $297 or $1497 plans")
                score -= 15
        except Exception:
            log("Pricing consistency", "FAIL", "Invalid JSON in product spec")
            score -= 15

    # 3. Webhook / Checkout config
    whop_monetize = BASE_DIR / "whop_monetize.py"
    if whop_monetize.exists():
        if "WHOP_API_KEY" in whop_monetize.read_text(encoding="utf-8"):
            log("Checkout configuration", "PASS")
        else:
            log("Checkout configuration", "FAIL", "Missing WHOP_API_KEY handler")
            score -= 10
    
    # 4. Webhook verification
    server_path = REPO_ROOT / "server" / "index.js"
    if server_path.exists():
        s_content = server_path.read_text(encoding="utf-8")
        
        # Check Analytics
        if "app.post('/api/analytics/track'" in s_content:
            log("Analytics backend handler", "PASS")
        else:
            log("Analytics backend handler", "FAIL", "Frontend sends to /api/analytics/track which lacks a robust backend handler")
            score -= 5

        # Check Webhook
        if "WHOP_WEBHOOK_SECRET" in s_content and "/api/webhook/whop" in s_content:
            log("Webhook verification", "PASS")
        else:
            log("Webhook verification", "FAIL", "No Webhook secret / endpoint implemented for Whop")
            score -= 10
    else:
        log("Backend verification", "FAIL", "server/index.js not found")
        score -= 15

    # 5. Lifecycle automation cooldowns
    lifecycle_path = BASE_DIR / "whop_lifecycle_engage.py"
    if lifecycle_path.exists():
        l_content = lifecycle_path.read_text(encoding="utf-8")
        if "cooldown" in l_content.lower() or "last_emailed" in l_content:
            log("Lifecycle automation", "PASS")
        else:
            log("Lifecycle automation", "WARNING", "No cooldown logic detected, risk of spamming")
            score -= 5

    # 6. Dashboard data integrity
    dash_path = BASE_DIR / "whop_revenue_dashboard.py"
    if dash_path.exists():
        d_content = dash_path.read_text(encoding="utf-8")
        if "[MOCK]" not in d_content.upper():
            log("Dashboard data integrity", "PASS")
        else:
            log("Dashboard data integrity", "FAIL", "Dashboard hardcodes fake A/B test results without MOCK labels")
            score -= 10

    # 7. Webhook HMAC verification (real crypto, not just header presence)
    if server_path.exists():
        s_content = server_path.read_text(encoding="utf-8")
        if "timingSafeEqual" in s_content and "createHmac('sha256', secret)" in s_content \
                and "express.raw({ type: '*/*'" in s_content:
            log("Webhook HMAC signature verification", "PASS")
        else:
            log("Webhook HMAC signature verification", "FAIL",
                "Signature header checked but never cryptographically verified over raw body")
            score -= 15

    # 8. No fabricated testimonials on the landing page
    if landing_path.exists():
        content = landing_path.read_text(encoding="utf-8")
        fabricated = [n for n in ("Marcus Reynolds", "Sarah Jenkins") if n in content]
        if not fabricated:
            log("Landing page evidence honesty", "PASS")
        else:
            log("Landing page evidence honesty", "FAIL",
                f"Fabricated testimonials present: {fabricated}")
            score -= 20

    # 9. Canonical event store reachable + Revenue OS modules importable
    try:
        sys.path.insert(0, str(BASE_DIR))
        import whop_revenue_os  # noqa: F401
        import whop_governor    # noqa: F401
        import whop_experiments  # noqa: F401
        log("Revenue OS core modules import", "PASS")
    except Exception as e:
        log("Revenue OS core modules import", "FAIL", str(e))
        score -= 15

    cli_path = BASE_DIR / "whop.py"
    if cli_path.exists() and (BASE_DIR / "tests").exists():
        log("Control CLI + test suite presence", "PASS")
    else:
        log("Control CLI + test suite presence", "FAIL", "whop.py or MBM/Whop/tests missing")
        score -= 10

    # 10. Memberships endpoint scoping regression (the live 400 unauthorized bug)
    live_path = BASE_DIR / "whop_live.py"
    if live_path.exists():
        l_src = live_path.read_text(encoding="utf-8")
        if '"/memberships"' in l_src and '{"company_id": account_id}' in l_src \
                and '"account_id": ACCOUNT_ID' not in l_src:
            log("Memberships endpoint company_id scoping", "PASS")
        else:
            log("Memberships endpoint company_id scoping", "FAIL",
                "/memberships must be scoped by company_id (account_id caused HTTP 400)")
            score -= 15
    else:
        log("Memberships endpoint company_id scoping", "FAIL", "whop_live.py missing")
        score -= 15

    # 11. Snapshot protection semantics (never lose good live data)
    if live_path.exists():
        l_src = live_path.read_text(encoding="utf-8")
        needed = ("LIVE_VALID" in l_src and "LIVE_PARTIAL" in l_src
                  and "STALE_VALID" in l_src and "carry_forward_applied" in l_src
                  and "last_successful_sync" in l_src)
        mon_src = BASE_DIR / "whop_monetize.py"
        m_txt = mon_src.read_text(encoding="utf-8") if mon_src.exists() else ""
        honesty = "UNVERIFIED" in m_txt or "UNVERIFIED" in l_src
        if needed and honesty:
            log("Snapshot states + carry-forward + honest reporting", "PASS")
        else:
            log("Snapshot states + carry-forward + honest reporting", "FAIL",
                "missing explicit snapshot states / carry-forward / UNVERIFIED semantics")
            score -= 10

    # 12. CTA map: no dead buttons, all five live products buyable from a tracked page
    try:
        sys.path.insert(0, str(BASE_DIR))
        import whop_product_intel as wpi  # noqa: E402
        audit = wpi.audit_ctas()
        if audit["status"] == "PASS":
            log("Landing CTA mapping (no dead buttons, 5/5 products covered)", "PASS")
        else:
            log("Landing CTA mapping (no dead buttons, 5/5 products covered)", "FAIL",
                f"dead={audit['dead']} untracked={audit['untracked_checkouts']} "
                f"missing_products={audit['live_products_without_cta']}")
            score -= 10
    except Exception as e:
        log("Landing CTA mapping", "FAIL", str(e))
        score -= 10

    # 13. Cross-sell engine present and sane
    try:
        recs = wpi.recommend_next_product(None, [])
        owned = wpi.recommend_next_product(None, ["prod_L2MmMKYlE9LAv"])
        ok = (recs and isinstance(owned, list)
              and all("product" in r and "confidence" in r for r in recs + owned)
              and not any(r["product"] == "Revenue Audit Engine" for r in owned))
        if ok:
            log("Cross-sell recommendation engine", "PASS")
        else:
            log("Cross-sell recommendation engine", "FAIL",
                "recommendations missing fields or recommends an owned product")
            score -= 5
    except Exception as e:
        log("Cross-sell recommendation engine", "FAIL", str(e))
        score -= 5

    # 14. PRE-REVENUE mode wired into command center
    try:
        src_os = (BASE_DIR / "whop_revenue_os.py").read_text(encoding="utf-8")
        if "PRE_REVENUE" in src_os and "_live_status_block" in src_os:
            log("PRE-REVENUE dashboard mode", "PASS")
        else:
            log("PRE-REVENUE dashboard mode", "FAIL",
                "command center lacks zero-revenue status block")
            score -= 5
    except Exception as e:
        log("PRE-REVENUE dashboard mode", "FAIL", str(e))
        score -= 5

    # Output
    print("WHOP REVENUE QA")
    print("===============\n")
    for r in report:
        print(r)

    print(f"\nPRODUCTION READINESS: {max(0, score)}/100")

    if score < 100:
        print("\nISSUES DETECTED:")
        for r in report:
            if "FAIL" in r or "WARNING" in r:
                print(r)

    return score

if __name__ == "__main__":
    run_qa()
