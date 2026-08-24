"""
whop_product_intel.py — Commercial intelligence for the five LIVE Whop products
================================================================================
Account biz_UxlhGUdO9TpGb0. Every price/plan/checkout URL below was pulled
from the live Whop API on 2026-08-24 (GET /api/v2/plans?company_id=...) and is
re-verified by `whop_live.sync_live()` — nothing here is invented.

Evidence map for descriptions:
  DFY AI Employee Suite      <- whop_monetize.PRODUCTS prod_dfy_agency_team copy
                                ("all 15 AI agents ... weekly optimization")
  Property Intelligence API  <- whop_monetize.PRODUCTS prod_lead_stream_api copy
                                + MBM/LeadEngine/property_intel (real NPI/DCAD data)
  Revenue Audit Engine       <- whop_monetize.PRODUCTS prod_l39iYJFojPjBU copy
                                + whop_revenue_os gate/QA semantics
  AI Voice Agent Factory     <- whop_monetize.PRODUCTS prod_oGAtXGDcJsvJu copy
                                (Retell AI telephony agent factory)
  AI Video Clipping Engine   <- whop_monetize.PRODUCTS prod_TwaiFektWmoOS copy
                                (15-agent clipping pipeline)

UNKNOWN means "no evidence in repo or API" — never a guess.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# LIVE INVENTORY (verified via GET /api/v2/plans?company_id=biz_UxlhGUdO9TpGb0,
# HTTP 200 on 2026-08-24; re-synced automatically by whop_live.sync_live())
# ─────────────────────────────────────────────────────────────────────────────

LIVE_INVENTORY = {
    "DFY AI Employee Suite": {
        "product_id": "prod_R5uDTAhXCKAcf",
        "plans": [{"plan_id": "plan_nqybZK0ZpJS3J", "type": "renewal",
                   "initial_price_usd": 1997.0, "renewal_price_usd": 1997.0,
                   "billing_period_days": 30, "currency": "USD",
                   "checkout_url": "https://whop.com/checkout/plan_nqybZK0ZpJS3J"}],
    },
    "Property Intelligence API": {
        "product_id": "prod_hseWnnhfVigJo",
        "plans": [{"plan_id": "plan_T6t6iMlvJvE9e", "type": "renewal",
                   "initial_price_usd": 97.0, "renewal_price_usd": 97.0,
                   "billing_period_days": 30, "currency": "USD",
                   "checkout_url": "https://whop.com/checkout/plan_T6t6iMlvJvE9e"}],
    },
    "Revenue Audit Engine": {
        "product_id": "prod_L2MmMKYlE9LAv",
        "plans": [{"plan_id": "plan_Sg0oIq3Tf4rlQ", "type": "one_time",
                   "initial_price_usd": 149.0, "renewal_price_usd": None,
                   "billing_period_days": None, "currency": "USD",
                   "checkout_url": "https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ"}],
    },
    "AI Voice Agent Factory": {
        "product_id": "prod_Y8rcA2dgkbxyZ",
        "plans": [{"plan_id": "plan_ZtH6wc9mYpl3j", "type": "renewal",
                   "initial_price_usd": 297.0, "renewal_price_usd": 297.0,
                   "billing_period_days": 30, "currency": "USD",
                   "checkout_url": "https://whop.com/checkout/plan_ZtH6wc9mYpl3j"}],
    },
    "AI Video Clipping Engine": {
        "product_id": "prod_MaHYZkh3AfEEf",
        "plans": [
            {"plan_id": "plan_KkeWhWGi53doc", "type": "renewal",
             "initial_price_usd": 497.0, "renewal_price_usd": 497.0,
             "billing_period_days": 30, "currency": "USD",
             "checkout_url": "https://whop.com/checkout/plan_KkeWhWGi53doc"},
            {"plan_id": "plan_HzmxF6LtJcoEG", "type": "renewal",
             "initial_price_usd": 997.0, "renewal_price_usd": 997.0,
             "billing_period_days": 30, "currency": "USD",
             "checkout_url": "https://whop.com/checkout/plan_HzmxF6LtJcoEG"},
        ],
    },
}

PRODUCT_IDS = {v["product_id"]: k for k, v in LIVE_INVENTORY.items()}

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4: PRODUCT INTELLIGENCE TABLE
# ─────────────────────────────────────────────────────────────────────────────

PRODUCT_INTEL = [
    {
        "product": "Revenue Audit Engine",
        "product_id": "prod_L2MmMKYlE9LAv",
        "current_price_usd": 149.0,
        "price_source": "REAL (live Whop plan plan_Sg0oIq3Tf4rlQ)",
        "billing_model": "one_time",
        "description": ("Revenue Review & Data Quality Audit Engine. Hourly revenue "
                        "accountability gate, reply + bounce detection, enforcer audits. "
                        "A real money verdict on your pipeline, not vanity metrics."),
        "target_customer": "Owner/operators already spending on leads/outreach who suspect leakage",
        "core_problem": "No honest measurement of which leads/replies/bounces turn into money",
        "promise": "A verdict: where your revenue leaks and what to fix first (72h)",
        "delivery_method": "Run against your pipeline data; written audit report",
        "fulfillment_cost": "UNKNOWN",
        "margin": "UNKNOWN",
        "upsell": "AI Voice Agent Factory (fix the calling gap the audit exposes)",
        "downsell": None,
        "recurring_opportunity": "Weekly audit retainer (natural; not yet priced)",
        "capacity": "HIGH (software-run)",
        "status": "LIVE",
    },
    {
        "product": "Property Intelligence API",
        "product_id": "prod_hseWnnhfVigJo",
        "current_price_usd": 97.0,
        "price_source": "REAL (live Whop plan plan_T6t6iMlvJvE9e)",
        "billing_model": "renewal_monthly",
        "description": ("Direct API feed of distressed-property and business-owner "
                        "intelligence: fresh auctions, county ownership verification, "
                        "NPI-verified business contacts. Blocked sources return blocked, "
                        "never fabricated rows."),
        "target_customer": "Real estate investors, wholesalers, agents, B2B lead buyers",
        "core_problem": "Buying stale/fabricated lead lists with dead phones",
        "promise": "Fresh, source-verified property & owner intelligence on demand",
        "delivery_method": "REST API + scheduled packs (property_intel pipeline)",
        "fulfillment_cost": "UNKNOWN (infra + scraping/API costs scale with usage)",
        "margin": "UNKNOWN",
        "upsell": "AI Voice Agent Factory (dial the feed) -> DFY AI Employee Suite",
        "downsell": None,
        "recurring_opportunity": ("STRONG — ongoing fresh data is the value; monthly "
                                  "renewal is native"),
        "capacity": "MEDIUM (source rate limits: DCAD/ArcGIS/RapidAPI quotas)",
        "status": "LIVE",
    },
    {
        "product": "AI Voice Agent Factory",
        "product_id": "prod_Y8rcA2dgkbxyZ",
        "current_price_usd": 297.0,
        "price_source": "REAL (live Whop plan plan_ZtH6wc9mYpl3j)",
        "billing_model": "renewal_monthly",
        "description": ("Deploy outbound AI phone agents that dial, qualify, and book — "
                        "no human dialers. Retell-based agent factory, skip-tracing + "
                        "power-dialing config included."),
        "target_customer": "Service businesses & investors with leads but no dialing capacity",
        "core_problem": "Leads go cold because nobody calls within 5 minutes, 7 times",
        "promise": "An AI caller working your list daily without hiring reps",
        "delivery_method": "Configured voice agents + dialer bridge (close_queue_dialer)",
        "fulfillment_cost": "UNKNOWN (telephony minutes bill per usage)",
        "margin": "UNKNOWN",
        "upsell": "DFY AI Employee Suite (full managed installation)",
        "downsell": "Property Intelligence API (data-only while they self-dial)",
        "recurring_opportunity": ("STRONG — ongoing dialing/optimization + per-minute "
                                  "usage justifies monthly renewal"),
        "capacity": "MEDIUM (voice model + telephony concurrency limits)",
        "status": "LIVE",
    },
    {
        "product": "AI Video Clipping Engine",
        "product_id": "prod_MaHYZkh3AfEEf",
        "current_price_usd": "497.0 / 997.0 (two live plans: plan_KkeWhWGi53doc / plan_HzmxF6LtJcoEG)",
        "price_source": "REAL (live Whop plans)",
        "billing_model": "renewal_monthly (two tiers)",
        "description": ("Turn 1 hour of long-form video into 20+ scroll-stopping clips — "
                        "automated. 15-agent pipeline: transcribe, cut, enhance "
                        "(sharpen/color/denoise/upscale), QC, deliver to TikTok/Shorts/Reels."),
        "target_customer": "Creators, coaches, brands with long-form content wanting shorts distribution",
        "core_problem": "Long-form sits unpromoted; manual clipping is slow and expensive",
        "promise": "Automated short-form output pipeline running on your footage monthly",
        "delivery_method": "Clipping-factory Docker pipeline + delivery agents",
        "fulfillment_cost": "UNKNOWN (GPU/render time scales with volume)",
        "margin": "UNKNOWN",
        "upsell": "DFY AI Employee Suite (clipping becomes one employee among many)",
        "downsell": None,
        "recurring_opportunity": ("STRONG — content keeps coming every month, so the "
                                  "pipeline must keep running"),
        "capacity": "MEDIUM (render workers bounded)",
        "status": "LIVE",
    },
    {
        "product": "DFY AI Employee Suite",
        "product_id": "prod_R5uDTAhXCKAcf",
        "current_price_usd": 1997.0,
        "price_source": "REAL (live Whop plan plan_nqybZK0ZpJS3J)",
        "billing_model": "renewal_monthly",
        "description": ("Complete custom installation of all 15 AI agents: automated video "
                        "clipping, Retell AI telephony, lead hunting, CRM revenue gate. "
                        "Includes priority support and weekly optimization."),
        "target_customer": "Established businesses ready to delegate whole functions to AI",
        "core_problem": "Needs multiple AI capabilities but lacks time/skills to integrate them",
        "promise": "A managed AI team installed and optimized for your business weekly",
        "delivery_method": "Done-for-you installation + managed retainer operations",
        "fulfillment_cost": "UNKNOWN (highest: human-managed multi-system ops)",
        "margin": "UNKNOWN",
        "upsell": None,
        "downsell": "AI Voice Agent Factory or AI Video Clipping Engine (single-function)",
        "recurring_opportunity": ("NATIVE — it IS a managed service; renewal is the product"),
        "capacity": "LOW (done-for-you installs are operator-time bound)",
        "status": "LIVE",
    },
]

_BY_ID = {row["product_id"]: row for row in PRODUCT_INTEL}
_BY_NAME = {row["product"]: row for row in PRODUCT_INTEL}

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: POSITIONING + actual hierarchy (derived from price & economics)
# ─────────────────────────────────────────────────────────────────────────────

POSITIONING = {
    "Revenue Audit Engine": {
        "who_should_buy": "Anyone already buying leads or running outreach",
        "why_they_buy": "Cheapest way to get an honest money verdict ($149 one-time)",
        "outcome_wanted": "Know exactly where revenue leaks before spending more",
        "differentiator": "Gate/enforcer logic we run hourly on our own pipeline",
        "buy_next": ["AI Voice Agent Factory", "Property Intelligence API"],
    },
    "Property Intelligence API": {
        "who_should_buy": "Investors/lead buyers who need fresh verified data",
        "why_they_buy": "$97/mo undercuts stale list vendors; source-verifiable rows",
        "outcome_wanted": "Dialable, real contacts instead of recycled junk lists",
        "differentiator": "Government registries + county ownership verify; blocked != mocked",
        "buy_next": ["AI Voice Agent Factory", "Revenue Audit Engine"],
    },
    "AI Voice Agent Factory": {
        "who_should_buy": "Businesses with leads but no calling capacity",
        "why_they_buy": "$297/mo replaces a $3k+/mo SDR attempt",
        "outcome_wanted": "More booked conversations from the list they already own",
        "differentiator": "Same agent factory we run on 1,222+ verified businesses",
        "buy_next": ["DFY AI Employee Suite"],
    },
    "AI Video Clipping Engine": {
        "who_should_buy": "Content brands sitting on long-form footage",
        "why_they_buy": "$497-$997/mo vs $2-5k/mo editing agencies",
        "outcome_wanted": "Consistent shorts distribution without an editor",
        "differentiator": "15-agent enhance/QC/deliver pipeline, not a human freelancer",
        "buy_next": ["DFY AI Employee Suite"],
    },
    "DFY AI Employee Suite": {
        "who_should_buy": "Businesses wanting whole functions delegated to AI",
        "why_they_buy": "One install covers clipping + telephony + lead hunting + CRM gate",
        "outcome_wanted": "Operate like a scaled team without hiring",
        "differentiator": "Managed weekly optimization on production systems we run ourselves",
        "buy_next": [],
    },
}

# Actual structure (not forced labels): two entry doors, one flagship.
#   DIAGNOSTIC DOOR  Revenue Audit Engine $149 one-time (lowest friction)
#   DATA DOOR        Property Intelligence API $97/mo (cheapest recurring)
#   CORE             AI Voice Agent Factory $297/mo
#   SPECIALIZED      AI Video Clipping Engine $497/$997/mo
#   FLAGSHIP         DFY AI Employee Suite $1997/mo
PRODUCT_LADDER = [
    {"step": "ENTRY_DIAGNOSTIC", "product": "Revenue Audit Engine",
     "price_usd": 149.0, "note": "one-time, risk-reversed door"},
    {"step": "ENTRY_DATA", "product": "Property Intelligence API",
     "price_usd": 97.0, "note": "lowest recurring commitment"},
    {"step": "CORE", "product": "AI Voice Agent Factory",
     "price_usd": 297.0, "note": "first automation engine; uses the data door's feed"},
    {"step": "SPECIALIZED", "product": "AI Video Clipping Engine",
     "price_usd": [497.0, 997.0], "note": "content vertical; independent of telephony"},
    {"step": "FLAGSHIP_RECURRING", "product": "DFY AI Employee Suite",
     "price_usd": 1997.0, "note": "managed everything; terminal step of the ladder"},
]

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: CROSS-SELL MATRIX
# Validated against product economics (data feeds callers, audits precede builds,
# single engines roll up into the suite).
# ─────────────────────────────────────────────────────────────────────────────

CROSS_SELL_MATRIX = {
    "Revenue Audit Engine": [
        ("AI Voice Agent Factory", "audit exposes missed-call revenue; voice agent fixes it",
         0.75),
        ("Property Intelligence API", "audit shows lead-quality gaps; verified feed closes them",
         0.65),
    ],
    "Property Intelligence API": [
        ("AI Voice Agent Factory", "a verified feed is only monetized once someone dials it",
         0.80),
        ("Revenue Audit Engine", "measure whether dialed feed converts before scaling spend",
         0.60),
    ],
    "AI Voice Agent Factory": [
        ("DFY AI Employee Suite", "proven caller -> delegate the rest of the stack",
         0.70),
        ("Property Intelligence API", "agents burn through lists; keep them fed with fresh data",
         0.60),
    ],
    "AI Video Clipping Engine": [
        ("DFY AI Employee Suite", "clipping customers already trust the agent pipeline",
         0.55),
    ],
    "DFY AI Employee Suite": [],
}


def recommend_next_product(customer=None, owned_products=None) -> list:
    """Return ranked next-product recommendations.

    customer: dict (optional; may carry lifecycle_state / business_type hints)
    owned_products: iterable of product names or product ids already owned
    Returns [{product, reason, confidence}] sorted by confidence desc.
    Never recommends a product already owned. Unknown owned ids are ignored.
    """
    owned = set()
    for item in (owned_products or []):
        if item in _BY_NAME:
            owned.add(item)
        elif item in PRODUCT_IDS:
            owned.add(PRODUCT_IDS[item])
    recs = []
    seen_products = set()
    for owned_name in _ordered_owned(owned):
        for target, reason, conf in CROSS_SELL_MATRIX.get(owned_name, []):
            if target in owned or target in seen_products:
                continue
            recs.append({"product": target, "reason": reason,
                         "confidence": conf})
            seen_products.add(target)
    # No ownership yet -> entry doors only (never push the flagship cold).
    if not recs:
        recs.append({"product": "Revenue Audit Engine",
                     "reason": "lowest-friction diagnostic entry ($149 one-time)",
                     "confidence": 0.7})
        recs.append({"product": "Property Intelligence API",
                     "reason": "cheapest recurring data door ($97/mo)",
                     "confidence": 0.55})
    recs.sort(key=lambda r: r["confidence"], reverse=True)
    return recs


def _ordered_owned(owned):
    order = ["DFY AI Employee Suite", "AI Video Clipping Engine",
             "AI Voice Agent Factory", "Property Intelligence API",
             "Revenue Audit Engine"]
    return [name for name in order if name in owned]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 8: RECURRING REVENUE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

RECURRING_ANALYSIS = {
    "Revenue Audit Engine": {
        "recurring_candidate": True,
        "why": "pipelines drift; a weekly/monthly re-audit has genuine ongoing value",
        "delivery_requirement": "scheduled runs against refreshed pipeline data",
        "expected_retention_reason": "each new audit finds new leaks as spend grows",
        "risk": "audit fatigue if findings repeat; must surface NEW issues each cycle",
    },
    "Property Intelligence API": {
        "recurring_candidate": True,
        "why": "data decays weekly; freshness is the entire product",
        "delivery_requirement": "scheduled ingestion + verification pipeline uptime",
        "expected_retention_reason": "stopping = list goes stale = calls fail",
        "risk": "upstream source blocking (Incapsula, RapidAPI 429s observed)",
    },
    "AI Voice Agent Factory": {
        "recurring_candidate": True,
        "why": "calling happens continuously; agents need monitoring/tuning",
        "delivery_requirement": "telephony infra + script iteration + answer-rate reports",
        "expected_retention_reason": "booked appointments keep renewing the ROI story",
        "risk": "per-minute telephony cost can erode margin at high volume",
    },
    "AI Video Clipping Engine": {
        "recurring_candidate": True,
        "why": "new footage arrives weekly; pipeline must run continuously",
        "delivery_requirement": "render workers + brand profiles + delivery destinations",
        "expected_retention_reason": "distribution cadence depends on steady clip supply",
        "risk": "platform policy changes on shorts spam; render cost spikes",
    },
    "DFY AI Employee Suite": {
        "recurring_candidate": True,
        "why": "it is literally a managed retainer (weekly optimization promised)",
        "delivery_requirement": "operator hours + all underlying subsystem SLAs",
        "expected_retention_reason": "ripping out a working AI team mid-operation hurts",
        "risk": "operator capacity caps growth; churn = full-suite loss",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 13: FIRST REVENUE OBJECTIVE
# Chosen on evidence: $149 one-time = lowest friction of the five live products;
# outreach infrastructure (prospects pool, scripts, follow-up sequence, GTM
# scoreboard) already targets exactly this buyer.
# ─────────────────────────────────────────────────────────────────────────────

FIRST_REVENUE_OBJECTIVE = {
    "objective_id": "FIRST_VERIFIED_PURCHASE",
    "product": "Revenue Audit Engine",
    "product_id": "prod_L2MmMKYlE9LAv",
    "plan_id": "plan_Sg0oIq3Tf4rlQ",
    "target_audience": ("Local service businesses & real estate investors already "
                        "spending on lead gen (ai-consultancy-agency/prospects_pool.csv "
                        "segments; MBM outreach lists)"),
    "offer": ("72h revenue-leakage audit of your current pipeline: where replies, "
              "bounces and missed calls bleed money — fixed-price, no retainer"),
    "price_usd": 149.0,
    "CTA": "START $149 AUDIT",
    "landing_path": "public/productized-service/ai-consultancy-sprint/landing.html#engines",
    "success_event": ("purchase event in logs/revenue_events.jsonl with "
                      "metadata.product_id == 'prod_L2MmMKYlE9LAv'"),
    "checkout_url": "https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ",
    "expected_revenue": "NOT_PROJECTED (do not fabricate forecasts)",
}

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 14: REVENUE OPPORTUNITY QUEUE (acquisition-first; zero verified customers)
# ─────────────────────────────────────────────────────────────────────────────

OPPORTUNITY_QUEUE = [
    {
        "rank": 1, "objective": "FIRST_PURCHASE",
        "detail": "Sell ONE Revenue Audit Engine ($149) via existing outreach assets",
        "required_infrastructure": ["tracked CTA on landing page", "webhook purchase event"],
        "current_status": "INFRA_READY" ,
        "blocker": "no traffic pointed at the tracked CTA yet",
        "next_action": ("send DAY_1_DIRECT_OUTREACH sequence with the $149 checkout link "
                        "as primary CTA"),
    },
    {
        "rank": 2, "objective": "FIRST_REPEAT_PURCHASE",
        "detail": "Audit buyer buys a second product within 45 days",
        "required_infrastructure": ["cross-sell recommendation", "post-delivery follow-up"],
        "current_status": "LOGIC_READY_NO_CUSTOMERS",
        "blocker": "requires FIRST_PURCHASE",
        "next_action": "after first purchase, trigger recommend_next_product() follow-up email",
    },
    {
        "rank": 3, "objective": "FIRST_SUBSCRIPTION",
        "detail": "First monthly renewal survives its first billing cycle",
        "required_infrastructure": ["subscription_started webhook path", "monitor scan"],
        "current_status": "WEBHOOK_MAPPING_READY",
        "blocker": "requires any recurring-plan purchase",
        "next_action": "pitch Property Intelligence API as the natural subscription after audit",
    },
    {
        "rank": 4, "objective": "FIRST_REFERRAL",
        "detail": "First member-driven referral signup",
        "required_infrastructure": ["Whop member affiliate program enabled (20%)"],
        "current_status": "AFFILIATE_CONFIG_IN_REPO",
        "blocker": "needs >=1 member to refer; affiliate apply command not yet run on this account",
        "next_action": "run `python MBM/Whop/whop_monetize.py affiliate` against biz_UxlhGUdO9TpGb0",
    },
    {
        "rank": 5, "objective": "FIRST_B2B_CUSTOMER",
        "detail": "First DFY AI Employee Suite ($1997/mo) contract",
        "required_infrastructure": ["case study material", "capacity plan", "onboarding SOP"],
        "current_status": "BLOCKED_UNTIL_TRACK_RECORD",
        "blocker": "no delivered customer outcomes documented yet (honesty rule)",
        "next_action": "convert first audit + voice customers; publish their results",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 10: LANDING PAGE CTA MAPPING
# Parses the real landing pages for checkout anchors and maps each to a product.
# Offline-safe: no network needed to build the table.
# ─────────────────────────────────────────────────────────────────────────────

LANDING_PAGES = [
    REPO_ROOT / "public" / "productized-service" / "ai-consultancy-sprint" / "landing.html",
    REPO_ROOT / "public" / "sprint" / "index.html",
]

# Legacy sprint checkouts live on the OTHER account (biz_2VDyenKpD0KOyo) and are
# still genuinely purchasable — mapped so no button is treated as fake/dead.
LEGACY_CHECKOUT_MAP = {
    "plan_e3ibiYXeeAaZV": {"product": "AI Consultancy Sprint Audit",
                           "account": "biz_2VDyenKpD0KOyo", "price_hint": 297},
    "plan_j5bQuNA8nRbWo": {"product": "AI Consultancy Build & Deploy",
                           "account": "biz_2VDyenKpD0KOyo", "price_hint": 1497},
    "plan_GM82PrzSTSmmK": {"product": "Managed AI Growth",
                           "account": "biz_2VDyenKpD0KOyo", "price_hint": 497},
}

_ANCHOR_RE = re.compile(r'<a[^>]+class="[^"]*track-cta[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                        re.IGNORECASE | re.DOTALL)


def build_cta_map(pages=None) -> list:
    """Extract every tracked CTA and classify where it actually goes."""
    pages = pages if pages is not None else LANDING_PAGES
    known_checkout_urls = {}
    for row in PRODUCT_INTEL:
        plans = LIVE_INVENTORY[row["product"]]["plans"]
        for pl in plans:
            known_checkout_urls[pl["checkout_url"]] = {
                "product": row["product"], "product_id": row["product_id"],
                "plan_id": pl["plan_id"], "account": "biz_UxlhGUdO9TpGb0"}
    for plan_id, meta in LEGACY_CHECKOUT_MAP.items():
        known_checkout_urls[f"https://whop.com/checkout/{plan_id}"] = {
            "product": meta["product"], "product_id": None,
            "plan_id": plan_id, "account": meta["account"]}

    rows = []
    for page in pages:
        page_path = Path(page)
        if not page_path.exists():
            continue
        html = page_path.read_text(encoding="utf-8")
        try:
            rel_page = str(page_path.relative_to(REPO_ROOT))
        except ValueError:
            rel_page = str(page)
        for url, text in _ANCHOR_RE.findall(html):
            label = re.sub(r"<[^>]+>", "", text).strip()
            info = known_checkout_urls.get(url)
            if info:
                status = "OK_CHECKOUT_LIVE"
                target = info["product"]
                product_id = info["product_id"]
                account = info["account"]
            elif url.startswith("#"):
                status = "OK_LEAD_CAPTURE_OR_ANCHOR"
                target = "internal"
                product_id = None
                account = None
            elif "mailto:" in url:
                status = "OK_LEAD_CAPTURE_EMAIL"
                target = "lead_capture"
                product_id = None
                account = None
            elif url.startswith("http"):
                status = "REVIEW_EXTERNAL"
                target = "external"
                product_id = None
                account = None
            else:
                status = "DEAD"
                target = None
                product_id = None
                account = None
            events = []
            if status.startswith("OK_CHECKOUT"):
                events = ["cta_click", "checkout_started"]
            elif status.startswith("OK_"):
                events = ["cta_click"]
            rows.append({
                "page": rel_page,
                "cta_text": label,
                "target_product": target,
                "product_id": product_id,
                "url": url,
                "tracking_event": "+".join(events),
                "status": status,
                "account": account,
            })
    return rows


def audit_ctas(rows=None) -> dict:
    """Aggregate CTA health. DEAD buttons or untracked checkouts fail the audit."""
    rows = rows if rows is not None else build_cta_map()
    dead = [r for r in rows if r["status"] == "DEAD"]
    review = [r for r in rows if r["status"] == "REVIEW_EXTERNAL"]
    checkout_rows = [r for r in rows if r["status"].startswith("OK_CHECKOUT")]
    untracked = [r for r in checkout_rows if "checkout_started" not in r["tracking_event"]]
    five_covered = {r["product_id"] for r in rows if r.get("product_id")}
    missing = [pid for pid in PRODUCT_IDS if pid not in five_covered]
    return {
        "total_tracked_ctas": len(rows),
        "dead": len(dead),
        "review_external": len(review),
        "live_checkout_ctas": len(checkout_rows),
        "untracked_checkouts": len(untracked),
        "live_products_without_cta": missing,
        "status": ("FAIL" if dead or untracked or missing
                   else ("PARTIAL" if review else "PASS")),
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Funnel helper (Phase 11): per-product funnel view over canonical events
# ─────────────────────────────────────────────────────────────────────────────

FUNNEL_EVENT_STEPS = ["landing_view", "cta_click", "checkout_started",
                      "purchase", "subscription_started"]


def funnel_by_product(events) -> dict:
    """Group canonical events by metadata.product_id (or cta_map fallback)."""
    out = {pid: {step: 0 for step in FUNNEL_EVENT_STEPS}
           for pid in PRODUCT_IDS}
    out["unattributed"] = {step: 0 for step in FUNNEL_EVENT_STEPS}
    for e in events or []:
        meta = e.get("metadata") or {}
        pid = meta.get("product_id") or PRODUCT_IDS.get(meta.get("product"))
        name = e.get("event_name")
        if name == "checkout_completed":
            name = "purchase"
        if name not in FUNNEL_EVENT_STEPS:
            continue
        key = pid if pid in out else "unattributed"
        out[key][name] += 1
    return out


def intel_summary() -> dict:
    """Compact machine-readable payload used by CLI/dashboard/tests."""
    return {
        "products": PRODUCT_INTEL,
        "ladder": PRODUCT_LADDER,
        "positioning": POSITIONING,
        "cross_sell_matrix": {k: [{"product": t, "reason": r, "confidence": c}
                                  for t, r, c in v]
                              for k, v in CROSS_SELL_MATRIX.items()},
        "recurring_analysis": RECURRING_ANALYSIS,
        "first_revenue_objective": FIRST_REVENUE_OBJECTIVE,
        "opportunity_queue": OPPORTUNITY_QUEUE,
        "live_inventory_source": "GET /api/v2/plans?company_id=biz_UxlhGUdO9TpGb0 (2026-08-24)",
    }


if __name__ == "__main__":
    print(json.dumps(intel_summary(), indent=2, default=str))
