"""
whop_monetize.py — Whop monetization automation for Contec AI Agentic Teamz
===========================================================================
Turns the (currently hidden, zero-member) Whop store into a money machine and
feeds real sales back into the revenue tracker.

Subcommands:
  publish     Publish products + create subscription plans (idempotent)
  checkout    Create prefilled checkout configurations for flagship plans
  affiliate   Enable the account affiliate program + feature a product
  report      Pull REAL Whop revenue signals -> logs/whop_revenue.json
  status      Print account/products/plans/memberships snapshot

Auth modes:
  REST  — uses WHOP_API_KEY env against https://api.whop.com/api/v1 (for CI)
  CLI   — shells out to the installed `whop` CLI (local, already authed)

Output contract follows AGENTS.md.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

WHOP_API_URL = os.getenv("WHOP_API_URL", "https://api.whop.com/api/v1")
ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "biz_2VDyenKpD0KOyo")
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent.parent / ".env.local")
    WHOP_API_KEY = os.getenv("WHOP_API_KEY", WHOP_API_KEY)
except Exception:
    pass

# ─── Product + pricing config (from HUNTER sprint mission pricing) ───
PRODUCTS = [
    {
        "id": "prod_TwaiFektWmoOS",
        "headline": "Turn 1 hour of long-form video into 20+ scroll-stopping clips — automated.",
        "description": (
            "AI Short-Form Content Engine. 15 agents: campaign hunt, acquire, transcribe, "
            "cut, enhance (sharpen/color/denoise/upscale), QC, and deliver to TikTok / "
            "Shorts / Reels. Starts from $497/mo. Cancel anytime."
        ),
        "plans": [
            {"title": "Starter", "initial_price": 497, "plan_type": "renewal", "billing_period": 30},
            {"title": "Growth", "initial_price": 997, "plan_type": "renewal", "billing_period": 30},
            {"title": "Annual (discounted)", "initial_price": 2490, "plan_type": "renewal", "billing_period": 365},
        ],
    },
    {
        "id": "prod_oGAtXGDcJsvJu",
        "headline": "Deploy AI phone agents that dial, qualify, and book — no human dialers.",
        "description": (
            "Retell AI Outbound Telephony Agent Factory. Deploy outbound AI agents from a "
            "config, run skip-tracing + power-dialing, capture answered leads. "
            "Starts from $297/mo. Cancel anytime."
        ),
        "plans": [
            {"title": "Starter", "initial_price": 297, "plan_type": "renewal", "billing_period": 30},
            {"title": "Scale", "initial_price": 997, "plan_type": "renewal", "billing_period": 30},
            {"title": "Annual (discounted)", "initial_price": 2490, "plan_type": "renewal", "billing_period": 365},
        ],
    },
    {
        "id": "prod_l39iYJFojPjBU",
        "headline": "Weekly revenue-gate audit of your lead pipeline — deals, replies, bounces.",
        "description": (
            "Revenue Review & Data Quality Audit Engine. Hourly revenue accountability gate, "
            "reply + bounce detection, enforcer audits. Get a real money verdict, not vanity "
            "metrics. From $149 one-time."
        ),
        "plans": [
            {"title": "One-time Audit", "initial_price": 149, "plan_type": "one_time", "billing_period": None},
            {"title": "Weekly", "initial_price": 497, "plan_type": "renewal", "billing_period": 30},
        ],
    },
]

ARCHIVED_PRODUCTS = [
    "prod_dYuivomWI72sk",
    "prod_eupgV6GneBBdt",
]

AFFILIATE_INSTRUCTIONS = (
    "Promote our AI automation engines (clipping, telephony, lead/revenue audit). "
    "Earn up to 30% recurring on every sale you refer. Share your checkout link — "
    "we handle onboarding and delivery."
)


def log(msg):
    line = f"[WHOP MONETIZE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))
    with open(LOGS_DIR / "whop_monetize.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ─── CLI mode (local, uses installed + authed whop CLI) ───
def _whop_bin():
    import shutil
    for cand in (os.getenv("WHOP_BIN"),
                 shutil.which("whop.cmd"),
                 shutil.which("whop-cli.cmd"),
                 shutil.which("whop")):
        if cand:
            return cand
    return "whop"


def run_whop(args, fmt="json"):
    cmd = [_whop_bin(), *args]
    if fmt:
        cmd += ["--format", fmt]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"whop {' '.join(args)} failed: {p.stdout[:300]} {p.stderr[:300]}")
    if not fmt:
        return p.stdout
    try:
        return json.loads(p.stdout)
    except Exception:
        # CLI may emit node warnings before JSON on Windows; find the JSON
        start = p.stdout.find("{")
        if start == -1:
            return {}
        return json.loads(p.stdout[start:])


def has_rest():
    return bool(WHOP_API_KEY)


def whop_rest(path, params=None, method="GET", body=None):
    import requests
    headers = {"Authorization": f"Bearer {WHOP_API_KEY}", "Content-Type": "application/json"}
    url = f"{WHOP_API_URL}{path}"
    r = requests.request(method, url, headers=headers, params=params, json=body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:300]}")
    if not r.text:
        return {}
    try:
        return r.json()
    except Exception:
        return {}


# ─── publish ───
def cmd_publish():
    """Publish flagship products and create subscription plans (idempotent)."""
    out = {"published": [], "plans_created": [], "skipped": []}
    existing_plans = []
    try:
        res = run_whop(["plans", "list", "--account_id", ACCOUNT_ID])
        existing_plans = res.get("data") or []
    except Exception as e:
        log(f"warn: could not list plans: {e}")
    plan_keys = {(p.get("product_id"), (p.get("title") or "").lower()) for p in existing_plans}

    for prod in PRODUCTS:
        pid = prod["id"]
        try:
            run_whop(["products", "update", pid,
                      "--headline", prod["headline"],
                      "--description", prod["description"]])
            run_whop(["products", "publish", pid])
            out["published"].append(pid)
            log(f"Published {prod['id']}")
        except Exception as e:
            out["skipped"].append(f"{pid}: {e}")
            log(f"publish {pid}: {e}")

        for plan in prod["plans"]:
            key = (pid, plan["title"].lower())
            if key in plan_keys:
                out["skipped"].append(f"{pid} / {plan['title']} (exists)")
                continue
            args = ["plans", "create", "--account_id", ACCOUNT_ID, "--product_id", pid,
                    "--title", plan["title"], "--plan_type", plan["plan_type"],
                    "--initial_price", str(plan["initial_price"]), "--currency", "usd",
                    "--release_method", "buy_now"]
            if plan.get("billing_period"):
                args += ["--billing_period", str(plan["billing_period"])]
                args += ["--renewal_price", str(plan["initial_price"])]
            try:
                res = run_whop(args)
                out["plans_created"].append(f"{pid} / {plan['title']} @ ${plan['initial_price']}")
                plan_keys.add(key)
                log(f"Created plan {plan['title']} @ ${plan['initial_price']} on {pid}")
            except Exception as e:
                out["skipped"].append(f"{pid} / {plan['title']}: {e}")
                log(f"plan {plan['title']} on {pid}: {e}")

    print(json.dumps(_contract("success", out)))
    return out


# ─── checkout ───
def cmd_checkout():
    """Create prefilled checkout configurations for every flagship plan."""
    out = {"created": [], "errors": []}
    try:
        plans = (run_whop(["plans", "list", "--account_id", ACCOUNT_ID]) or {}).get("data") or []
    except Exception as e:
        print(json.dumps(_contract("failure", {"error": str(e)})))
        return
    targets = {p["id"] for p in PRODUCTS}
    seen = set()
    try:
        existing = (run_whop(["checkout-configurations", "list", "--account_id", ACCOUNT_ID]) or {}).get("data") or []
        seen = {(c.get("plan_id")) for c in existing}
    except Exception:
        seen = set()

    for plan in plans:
        if plan.get("product_id") not in targets:
            continue
        if plan.get("id") in seen:
            continue
        try:
            run_whop(["checkout-configurations", "create",
                      "--account_id", ACCOUNT_ID,
                      "--plan_id", plan["id"],
                      "--mode", "payment"])
            out["created"].append(plan["id"])
            seen.add(plan["id"])
            log(f"Checkout config for {plan.get('title')}")
        except Exception as e:
            out["errors"].append(f"{plan.get('id')}: {e}")
    print(json.dumps(_contract("success" if not out["errors"] else "failure", out)))
    return out


# ─── affiliate ───
def cmd_affiliate():
    """Enable the account affiliate program and feature a flagship product."""
    featured = PRODUCTS[0]["id"]
    try:
        run_whop(["accounts", "update", ACCOUNT_ID,
                  "--affiliate_application_required", "false",
                  "--affiliate_instructions", AFFILIATE_INSTRUCTIONS,
                  "--featured_affiliate_product_id", featured,
                  "--description", "AI automation engines for content, telephony, and lead/revenue."])
        out = {"affiliate_enabled": True, "featured_product": featured}
        log(f"Affiliate program enabled, featuring {featured}")
    except Exception as e:
        out = {"affiliate_enabled": False, "error": str(e)}
        log(f"affiliate setup failed: {e}")
    print(json.dumps(_contract("success" if out.get("affiliate_enabled") else "failure", out)))
    return out


# ─── report ───
def cmd_report():
    """Gather REAL Whop revenue signals and write logs/whop_revenue.json."""
    out = {"timestamp": datetime.now(timezone.utc).isoformat(),
           "account_id": ACCOUNT_ID, "mode": "rest" if has_rest() else "cli",
           "memberships_active": 0, "members": 0, "net_revenue_7d": None,
           "products": [], "errors": []}

    def _try(fn):
        try:
            return fn()
        except Exception as e:
            out["errors"].append(str(e))
            return None

    if has_rest():
        res = _try(lambda: whop_rest("/memberships", {"account_id": ACCOUNT_ID, "status": "active", "first": 100}))
        if isinstance(res, dict):
            out["memberships_active"] = len(res.get("data") or res.get("memberships") or [])
        prods = _try(lambda: whop_rest("/products"))
        if isinstance(prods, dict):
            rows = prods.get("data") or []
            out["members"] = sum(p.get("member_count") or 0 for p in rows)
            out["products"] = [{"id": p.get("id"), "title": p.get("title"),
                                "member_count": p.get("member_count") or 0} for p in rows]
    else:
        res = _try(lambda: run_whop(["memberships", "list", "--account_id", ACCOUNT_ID, "--status", "active", "--first", "100"]))
        if isinstance(res, dict):
            out["memberships_active"] = len(res.get("data") or [])
        prods = _try(lambda: run_whop(["products", "list", "--account_id", ACCOUNT_ID]))
        if isinstance(prods, dict):
            rows = prods.get("data") or []
            out["members"] = sum(p.get("member_count") or 0 for p in rows)
            out["products"] = [{"id": p.get("id"), "title": p.get("title"),
                                "member_count": p.get("member_count") or 0} for p in rows]

    _save_json(LOGS_DIR / "whop_revenue.json", out)
    print(f"WHOP REVENUE: {json.dumps(out, default=str)}")
    print(json.dumps(_contract("success", out)))
    return out


# ─── status ───
def cmd_status():
    try:
        res = run_whop(["products", "list", "--account_id", ACCOUNT_ID])
        rows = res.get("data") or []
        print(f"ACCOUNT: {ACCOUNT_ID}")
        for r in rows:
            print(f"  {r.get('id')} | {r.get('visibility')} | members={r.get('member_count')} | {r.get('title')}")
    except Exception as e:
        print(f"status failed: {e}")
    try:
        res = run_whop(["memberships", "list", "--account_id", ACCOUNT_ID, "--first", "20"])
        rows = res.get("data") or []
        print(f"\nMEMBERSHIPS (recent): {len(rows)}")
        for r in rows[:10]:
            print(f"  {r.get('created_at')} | {r.get('status')} | {r.get('plan') or r.get('plan_id')}")
    except Exception as e:
        print(f"memberships failed: {e}")


def _contract(status, outputs, next_action="continue", owner="system"):
    return {
        "status": status,
        "inputs": {"account_id": ACCOUNT_ID, "mode": "rest" if has_rest() else "cli"},
        "outputs": outputs,
        "errors": outputs.get("errors") or outputs.get("skipped") or [],
        "next_action": next_action,
        "owner": owner,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


COMMANDS = {"publish": cmd_publish, "checkout": cmd_checkout,
            "affiliate": cmd_affiliate, "report": cmd_report, "status": cmd_status}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command '{cmd}'. Use one of: {', '.join(COMMANDS)}")
        sys.exit(1)
