"""
shopify_ai_recommender.py — AI Product Recommender & Upsell Engine.
===================================================================================
Subsystem: MBM Shopify E-Commerce Engine

Generates personalized cross-sell / upsell recommendations for a shopper's cart
and emits dynamic single-use 20% discount checkout links.

Routing (strongest available first):
1. Gemini API        — GEMINI_API_KEY (cloud, best quality)
2. Local LLM (Ollama) — qwen2.5-coder via mbm_social.model_registry
3. Rule-based fallback — deterministic co-purchase pairs (offline, always works)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR.parent.parent))
try:
    from MBM.Scripts.neteller_config import NETELLER_EMAIL, NETELLER_ACCOUNT_ID, neteller_link
except Exception:
    NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
    NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")

    def neteller_link(amount, item, currency="USD", **kw):
        base = "https://member.neteller.com/pay"
        return f"{base}?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount={float(amount):.2f}&currency={currency}&item={item}"


CATALOG_FILE = LOGS_DIR / "shopify_catalog.json"
RECS_FILE = LOGS_DIR / "recommendations.json"

DISCOUNT_PERCENT = 20

# Deterministic cross-sell pairs (rule-based fallback + Gemini prompt anchors).
CROSS_SELL_MAP = {
    "prod_ai_agent_suite": ["prod_clipping_sub_pro", "prod_lead_engine_pass"],
    "prod_clipping_sub_pro": ["prod_ai_agent_suite", "prod_enterprise_setup"],
    "prod_lead_engine_pass": ["prod_ai_agent_suite", "prod_clipping_sub_pro"],
    "prod_enterprise_setup": ["prod_clipping_sub_pro", "prod_ai_agent_suite"],
}


def _load_catalog() -> list:
    if CATALOG_FILE.exists():
        try:
            return json.loads(CATALOG_FILE.read_text(encoding="utf-8")).get("products", [])
        except Exception:
            pass
    # Inline catalog fallback so the engine never depends on a prior sync.
    from shopify_storefront_engine import FLAGSHIP_PRODUCTS
    return FLAGSHIP_PRODUCTS


def _find_product(products, cart_title):
    title = (cart_title or "").lower()
    for p in products:
        if title in p["title"].lower() or p["title"].lower() in title:
            return p
    return None


def _single_use_discount_link(product_id: str) -> str:
    """Build a dynamic 20%-off Neteller checkout link for a product."""
    try:
        p = next((x for x in _load_catalog() if x["id"] == product_id), None)
        if not p:
            return None
        discounted = round(p["price"] * (1 - DISCOUNT_PERCENT / 100.0), 2)
        return neteller_link(discounted, f"{p['id']}_UPSELL20")
    except Exception:
        return None


def _rule_based(cart_product, products):
    cand_ids = CROSS_SELL_MAP.get(
        cart_product["id"],
        [p["id"] for p in products if p["id"] != cart_product["id"]][:2],
    )
    recs = []
    for rec_id in cand_ids:
        p = next((x for x in products if x["id"] == rec_id), None)
        if not p:
            continue
        recs.append({
            "product_id": p["id"],
            "title": p["title"],
            "description": p.get("description", ""),
            "price": p["price"],
            "compare_at_price": p.get("compare_at_price"),
            "position": "crossSell",
            "discount_percent": DISCOUNT_PERCENT,
            "single_use_discount_link": _single_use_discount_link(p["id"]),
            "checkout_url": _checkout_url(p),
        })
    return recs[:2]


def _checkout_url(p):
    return p.get("checkout_url") or neteller_link(p.get("price", 0), f"{p.get('id', 'product')}")


def _load_env_value(key, default=""):
    for p in (BASE_DIR.parent.parent, BASE_DIR):
        for name in (".env", ".env.local"):
            f = p / name
            if f.exists():
                try:
                    for line in f.read_text(encoding="utf-8").splitlines():
                        if line.startswith(key + "=") and not line.startswith("#"):
                            return line.split("=", 1)[1].strip().strip('"')
                except Exception:
                    pass
    return default


def _gemini(cart_items, products):
    key = _load_env_value("GEMINI_API_KEY")
    if not key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    catalog_brief = "\n".join([f"- {p['id']}: {p['title']} @ ${p['price']}" for p in products])
    prompt = (
        f"Cart items: {json.dumps(cart_items)}\n"
        f"Catalog:\n{catalog_brief}\n"
        f"Pick the best 2 complementary cross-sell product_ids for the cart. "
        f"Return JSON: {{\"recommendation_ids\": [\"prod_x\", \"prod_y\"], \"reason\": \"...\"}}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        print(f"[AI RECOMMENDER] Gemini unavailable ({e}); trying local model")
        return None


def _local_ollama(cart_items, products):
    try:
        sys.path.insert(0, str(BASE_DIR.parent.parent / "clipping-factory" / "MBM-Social"))
        from mbm_social.model_registry import generate as _local_gen

        catalog_brief = "\n".join([f"- {p['id']}: {p['title']}" for p in products])
        prompt = (
            f"Cart items: {json.dumps(cart_items)}\nCatalog:\n{catalog_brief}\n"
            'Pick the best 2 complementary cross-sell product ids. Return JSON only '
            '{"recommendation_ids": ["prod_a","prod_b"]}'
        )
        out = _local_gen(prompt, task="strategy")
        import re

        m = re.search(r"\{.*\}", out, re.S)
        return json.loads(m.group(0) if m else out)
    except Exception as e:
        print(f"[AI RECOMMENDER] Local model failed ({e}); using rule-based")
        return None


def recommend(cart_items):
    products = _load_catalog()
    if not products:
        return {"status": "failure", "errors": ["No catalog available"]}

    cart_product = None
    for it in cart_items:
        p = _find_product(products, it.get("title"))
        if p:
            cart_product = p
            break
    if not cart_product:
        cart_product = products[0]
    cart_title = (cart_items[0].get("title") or cart_product["title"]) if cart_items else cart_product["title"]

    # Strongest-first recommendation source.
    choice = _gemini(cart_items, products)
    mode = "gemini"
    if choice is None:
        choice = _local_ollama(cart_items, products)
        mode = "local"
    if not choice or (choice.get("recommendation_ids") or []) == []:
        recs = _rule_based(cart_product, products)
        mode = "rule"
    else:
        ids = choice.get("recommendation_ids") or []
        recs = []
        for rid in ids:
            p = next((x for x in products if x["id"] == rid), None)
            if p:
                recs.append({
                    "product_id": p["id"],
                    "title": p["title"],
                    "price": p["price"],
                    "compare_at_price": p.get("compare_at_price"),
                    "discount_percent": DISCOUNT_PERCENT,
                    "single_use_discount_link": _single_use_discount_link(p["id"]),
                    "checkout_url": _checkout_url(p),
                    "reason": choice.get("reason", ""),
                })
        recs = recs[:2]

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cart_items": cart_items,
        "seat_product_id": cart_product["id"],
        "engine": mode,
        "recommendations": recs,
    }
    RECS_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[AI RECOMMENDER] engine={mode} -> {len(recs)} recs for cart '{cart_title}'")
    return {"status": "success", "inputs": {"cart_items": cart_items}, "outputs": out, "errors": [], "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    # Accept cart items either as a JSON arg or a single title.
    if len(sys.argv) > 1:
        try:
            cart = json.loads(sys.argv[1])
        except Exception:
            cart = [{"title": sys.argv[1], "quantity": 1}]
    else:
        cart = [{"title": "Contec AI Agentic Suite — Full License", "quantity": 1}]
    res = recommend(cart)
    print(json.dumps(res, indent=2))