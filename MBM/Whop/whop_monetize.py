"""
whop_monetize.py — Whop monetization automation for Contec AI Agentic Teamz
===========================================================================
Turns the (currently hidden, zero-member) Whop store into a money machine and
feeds real sales back into the revenue tracker.

Subcommands:
  logo        Upload + attach per-product logos (gallery images) — unblocks publish
  publish     Set logos, apply monetisation, publish products + create plans (idempotent)
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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

WHOP_API_URL = os.getenv("WHOP_API_URL", "https://api.whop.com/api/v1")
# SECURITY: never hardcode a real WHOP_ACCOUNT_ID. If env is missing, fail loud
# (better: the CLI auth subcommand guides the user to set it).
ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "")
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")

def _load_env():
    """Load WHOP_API_KEY from repo-root .env / .env.local without requiring dotenv."""
    for name in (".env", ".env.local"):
        env_file = BASE_DIR.parent.parent / name
        try:
            if not env_file.exists():
                continue
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("WHOP_API_KEY=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent.parent / ".env")
    load_dotenv(BASE_DIR.parent.parent / ".env.local")
    WHOP_API_KEY = os.getenv("WHOP_API_KEY", WHOP_API_KEY) or _load_env()
except Exception:
    WHOP_API_KEY = WHOP_API_KEY or _load_env()

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
    {
        "id": "prod_dfy_agency_team",
        "headline": "Done-For-You AI Employee Suite & Monthly Executive Managed Retainer.",
        "description": (
            "Complete custom installation of all 15 AI agents: automated video clipping, "
            "Retell AI telephony, lead hunting, and CRM revenue gate. Includes 24/7 priority support "
            "and weekly optimization."
        ),
        "plans": [
            {"title": "VIP DFY Setup", "initial_price": 2490, "plan_type": "one_time", "billing_period": None},
            {"title": "Managed Retainer", "initial_price": 1997, "plan_type": "renewal", "billing_period": 30},
        ],
    },
    {
        "id": "prod_lead_stream_api",
        "headline": "Live API Feed of Distressed Real Estate & B2B Buyer/Seller Opportunities.",
        "description": (
            "Direct API access to daily skip-traced lead packs (Dallas code violations, "
            "wholesaler directories, commercial permits) with 100% verified phone/email data."
        ),
        "plans": [
            {"title": "API Hobby Pass", "initial_price": 49, "plan_type": "renewal", "billing_period": 30},
            {"title": "API Monthly Pass", "initial_price": 997, "plan_type": "renewal", "billing_period": 30},
            {"title": "Annual Unlimited Pass", "initial_price": 2490, "plan_type": "renewal", "billing_period": 365},
        ],
    },
    {
        "id": "prod_crm_blueprints",
        "headline": "Agent-Ready CRM Workflow Blueprints (Make.com/n8n).",
        "description": (
            "Exportable JSON blueprints to instantly connect your CRM (GoHighLevel/HubSpot) "
            "to AI telephony and lead feeds."
        ),
        "plans": [
            {"title": "Digital Blueprint Download", "initial_price": 299, "plan_type": "one_time", "billing_period": None},
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

# Per-product logo artwork. Products are B2B AI services under the Contec AI
# Agentic Teamz umbrella, so the ClippingFactoryMBM brand mark is reused as the
# company logo. Swap paths to regenerate per-product logos later.
REPO_ROOT = BASE_DIR.parent.parent
LOGO_BY_PRODUCT = {
    "prod_TwaiFektWmoOS": REPO_ROOT / "clipping-factory" / "MBM-Social" / "Brands" / "clippingfactorymbm" / "profile.png",
    "prod_oGAtXGDcJsvJu": REPO_ROOT / "clipping-factory" / "MBM-Social" / "Brands" / "clippingfactorymbm" / "profile.png",
    "prod_l39iYJFojPjBU": REPO_ROOT / "clipping-factory" / "MBM-Social" / "Brands" / "clippingfactorymbm" / "profile.png",
}

# Monetisation levers applied to every flagship product.
AFFILIATE_PERCENTAGE = 20.0   # 20% recurring commission (global + member programs)
CUSTOM_CTA = "get_access"
CUSTOM_STATEMENT_DESCRIPTOR = "WHOP*CONTEAI"


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
    return None


def run_whop(args, fmt="json"):
    wb = _whop_bin()
    if not wb:
        raise RuntimeError("Whop CLI not found on system PATH and no WHOP_API_KEY set.")
    cmd = [wb, *args]
    if fmt:
        cmd += ["--format", fmt]
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
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
    r = requests.request(method, url, headers=headers, params=params, json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:300]}")
    if not r.text:
        return {}
    try:
        return r.json()
    except Exception:
        return {}


def upload_file(image_path):
    """Upload a local image via REST and return the Whop file id."""
    import requests
    if not image_path.exists():
        raise RuntimeError(f"logo file missing: {image_path}")
    filename = image_path.name
    res = whop_rest("/files", method="POST", body={"filename": filename, "visibility": "public"})
    file_id = res.get("id")
    upload_url = res.get("upload_url")
    if not file_id or not upload_url:
        raise RuntimeError(f"files create returned no upload target: {res}")
    headers = dict(res.get("upload_headers") or {})
    headers.setdefault("Content-Type", "image/png")
    with open(image_path, "rb") as fh:
        content = fh.read()
    up = requests.put(upload_url, data=content, headers=headers, timeout=180)
    if up.status_code >= 400:
        raise RuntimeError(f"file upload failed: {up.status_code} {up.text[:200]}")
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            status = whop_rest(f"/files/{file_id}", method="GET").get("upload_status")
        except Exception:
            status = None
        if status == "ready":
            break
        time.sleep(3)
    if status != "ready":
        raise RuntimeError(f"file {file_id} did not finish processing (status={status})")
    log(f"Uploaded {filename} -> {file_id} (ready)")
    return file_id


def set_product_logo(pid, file_id):
    """Attach a gallery image (the product logo/cover) via REST PATCH.

    The Whop Product schema has no dedicated ``logo`` field — the first
    ``gallery_images`` entry serves as the product's cover/logo for publishing.
    """
    whop_rest(f"/products/{pid}", method="PATCH",
              body={"gallery_images": [{"id": file_id}]})
    log(f"Logo (gallery image) attached to {pid}")


def product_has_logo(pid):
    """True when the product has at least one gallery image (publish gate)."""
    try:
        res = whop_rest(f"/products/{pid}", method="GET")
        return bool(res.get("gallery_images"))
    except Exception:
        return False


def apply_monetisation(pid):
    """Monetisation levers: affiliate programs, CTA, statement descriptor."""
    body = {
        "global_affiliate_status": "enabled",
        "global_affiliate_percentage": AFFILIATE_PERCENTAGE,
        "member_affiliate_status": "enabled",
        "member_affiliate_percentage": AFFILIATE_PERCENTAGE,
        "custom_cta": CUSTOM_CTA,
        "custom_statement_descriptor": CUSTOM_STATEMENT_DESCRIPTOR,
    }
    try:
        whop_rest(f"/products/{pid}", method="PATCH", body=body)
        log(f"Monetisation applied to {pid} (affiliate {AFFILIATE_PERCENTAGE}%, cta={CUSTOM_CTA})")
        return True
    except Exception as e:
        log(f"monetisation patch {pid} failed (continuing): {e}")
        return False


def publish_product(pid):
    """Publish via REST, falling back to CLI on scope failures."""
    if not product_has_logo(pid):
        raise RuntimeError(f"cannot publish {pid}: no logo set")
    try:
        whop_rest(f"/products/{pid}/publish", method="POST", body={})
        return
    except Exception as e:
        log(f"REST publish {pid} failed, trying CLI: {e}")
    run_whop(["products", "publish", pid])


# ─── logo ───
def cmd_logo():
    """Upload per-product logos and attach as gallery images (idempotent)."""
    out = {"logo_set": [], "skipped": [], "errors": []}
    for pid, path in LOGO_BY_PRODUCT.items():
        try:
            if product_has_logo(pid):
                out["skipped"].append(f"{pid} (logo exists)")
                continue
            file_id = upload_file(path)
            set_product_logo(pid, file_id)
            out["logo_set"].append(pid)
        except Exception as e:
            out["errors"].append(f"{pid}: {e}")
            log(f"logo {pid}: {e}")
    print(json.dumps(_contract("success" if not out["errors"] else "failure", out)))
    return out


# ─── publish ───
def cmd_publish():
    """Set logos, publish flagship products and create subscription plans (idempotent)."""
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
            if not product_has_logo(pid):
                file_id = upload_file(LOGO_BY_PRODUCT[pid])
                set_product_logo(pid, file_id)
            apply_monetisation(pid)
            publish_product(pid)
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
        run_whop(["accounts", "update", "--account_id", ACCOUNT_ID,
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
        prods = _try(lambda: whop_rest("/products", {"company_id": ACCOUNT_ID}))
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
    _telegram_digest(out)
    print(f"WHOP REVENUE: {json.dumps(out, default=str)}")
    print(json.dumps(_contract("success", out)))
    return out


def _telegram_digest(out):
    """Push a compact revenue/members digest to Telegram."""
    members = out.get("members") or 0
    active = out.get("memberships_active") or 0
    revenue = out.get("net_revenue_7d")
    rev_txt = f"${revenue}" if revenue is not None else "n/a"
    prods = out.get("products") or []
    lines = [f"<b>✅ Whop Digest</b>",
             f"Active memberships: {active}",
             f"Total members: {members}",
             f"Net revenue (7d): {rev_txt}",
             f"Products surfaced: {len(prods)}"]
    if out.get("errors"):
        real = [e for e in out["errors"] if "/memberships" not in str(e)]
        if real:
            lines.append(f"⚠️ {len(real)} errors — see logs")
    _send_telegram("\n".join(lines))


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


# ─── monitor (churn + lifecycle engagement scan) ───
# Risk/day thresholds. Tune after launch: most communities churn 10-15%/mo.
MONITOR_RISK_DAYS = 7        # renewal/expiry within this window => at-risk
MONITOR_DORMANT_DAYS = 14    # no payment/activity for this long on active => dormant
MONITOR_WELCOME_DAYS = 2     # created within this window => brand new (needs onboarding)


def _parse_ts(value):
    """Best-effort parse of a Whop timestamp string -> aware datetime or None."""
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _days_between(future_naive):
    """Need days until an (possibly timezone-less) datetime."""
    now = datetime.now(timezone.utc)
    if future_naive.tzinfo is None:
        future_naive = future_naive.replace(tzinfo=timezone.utc)
    return (future_naive - now).days


def _send_telegram(text):
    """Push a message to the configured Telegram chat (no-op if unset)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat, "text": text, "parse_mode": "HTML"},
                      timeout=15)
        return True
    except Exception as e:
        log(f"telegram alert failed: {e}")
        return False


def _classify_membership(m):
    """Bucket a membership into a lifecycle stage with risk flags."""
    created = _parse_ts(m.get("created_at"))
    expires = _parse_ts(m.get("expire_at") or m.get("expires_at") or m.get("expiry_at"))
    status = str(m.get("status") or "unknown").lower()

    if status in ("cancelled", "canceling", "expired", "refunded"):
        return {"stage": "churned", "risk": "high", "reason": f"status={status}"}
    if created is None and expires is None:
        return {"stage": "unknown", "risk": "unknown", "reason": "no timestamps"}

    now = datetime.now(timezone.utc)
    age_days = (now - created).days if created else None
    days_to_expiry = (expires - now).days if expires else None

    if age_days is not None and age_days <= MONITOR_WELCOME_DAYS:
        return {"stage": "new", "risk": "welcome", "reason": f"created {age_days}d ago"}
    if expires is not None and 0 <= days_to_expiry <= MONITOR_RISK_DAYS:
        return {"stage": "at_risk", "risk": "high", "reason": f"expires in {days_to_expiry}d"}
    if created is not None and age_days >= MONITOR_DORMANT_DAYS:
        return {"stage": "dormant", "risk": "medium", "reason": f"{age_days}d old, no touch"}
    return {"stage": "stable", "risk": "low", "reason": "healthy"}


def cmd_monitor():
    """Scan memberships into lifecycle buckets, write ledger, Telegram alert at-risk."""
    out = {"timestamp": datetime.now(timezone.utc).isoformat(),
           "account_id": ACCOUNT_ID,
           "total": 0, "by_stage": {}, "at_risk": [], "members": [], "new": [], "errors": []}
    try:
        res = run_whop(["memberships", "list", "--account_id", ACCOUNT_ID, "--first", "100"])
        memberships = res.get("data") or []
    except Exception as e:
        out["errors"].append(f"memberships list: {e}")
        memberships = []

    for m in memberships:
        out["total"] += 1
        cls = _classify_membership(m)
        out["by_stage"][cls["stage"]] = out["by_stage"].get(cls["stage"], 0) + 1
        entry = {"membership_id": m.get("id"), "plan_id": m.get("plan_id") or m.get("plan"),
                 "user_id": m.get("user_id"), "status": m.get("status"), **cls}
        if cls["stage"] == "at_risk":
            out["members"].append(entry)
        if cls["stage"] == "new":
            out["new"].append(entry)
        # ledger: keep a rolling per-membership log for the scheduler
        ledger = _load_json(LOGS_DIR / "whop_memberships.json")
        records = ledger.get("records", [])
        records.append({**entry, "scanned_at": out["timestamp"]})
        _save_json(LOGS_DIR / "whop_memberships.json", {"records": records[-2000:]})

    at_risk = out["members"]
    if at_risk:
        lines = [f"<b>🚨 Whop churn monitor</b> — {len(at_risk)} at-risk"]
        for e in at_risk[:15]:
            lines.append(f"• {e.get('membership_id')} | {e.get('reason')}")
        if len(at_risk) > 15:
            lines.append(f"… +{len(at_risk)-15} more")
        _send_telegram("\n".join(lines))

    print(f"WHOP MONITOR: total={out['total']} {json.dumps(out['by_stage'])}")
    print(json.dumps(_contract("success" if not out["errors"] else "failure", out)))
    return out


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


COMMANDS = {"logo": cmd_logo, "publish": cmd_publish, "checkout": cmd_checkout,
            "affiliate": cmd_affiliate, "report": cmd_report, "status": cmd_status,
            "monitor": cmd_monitor}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command '{cmd}'. Use one of: {', '.join(COMMANDS)}")
        sys.exit(1)
