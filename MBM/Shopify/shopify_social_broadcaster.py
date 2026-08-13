"""
shopify_social_broadcaster.py — Social-to-Shopify Promo Broadcaster.
===================================================================================
Subsystem: MBM Shopify E-Commerce Engine

Connects the HighReachViralityAgent to auto-generate video clips with CTA overlays
pointing to Shopify store products, then queues them into the MBM-Social
multi-channel publishing queue (`clipping-factory/MBM-Social/publish_queue/`).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SOCIAL_HOME = BASE_DIR.parent.parent / "clipping-factory" / "MBM-Social"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SOCIAL_HOME / "mbm_social"))
sys.path.insert(0, str(SOCIAL_HOME))

# Product -> promo CTA overlay mapping (title, hook, store URL, target niche).
STORE_PROMOS = [
    {
        "product_id": "prod_ai_agent_suite",
        "title": "Build Your AI Business Empire With The Contec Agent Suite",
        "cta": "Get The Full License → contec-ai-store.myshopify.com",
        "store_url": "https://contec-ai-store.myshopify.com/cart/40112233:1",
        "niche": "tech",
    },
    {
        "product_id": "prod_clipping_sub_pro",
        "title": "Automated 1080p60 Clips While You Sleep",
        "cta": "Start Clipping Factory Pro → $99/mo",
        "store_url": "https://contec-ai-store.myshopify.com/cart/40112234:1",
        "niche": "tech",
    },
    {
        "product_id": "prod_lead_engine_pass",
        "title": "300 Verified Real Estate Leads, Skip-Traced",
        "cta": "Grab The Lead Pack → $250",
        "store_url": "https://contec-ai-store.myshopify.com/cart/40112235:1",
        "niche": "realestate",
    },
    {
        "product_id": "prod_enterprise_setup",
        "title": "Custom AI Enterprise Deployment In 48 Hours",
        "cta": "Book Enterprise Setup → $1,499",
        "store_url": "https://contec-ai-store.myshopify.com/cart/40112236:1",
        "niche": "tech",
    },
]


def _flush_imports():
    """Ensure the HighReach path is importable regardless of CWD."""
    for p in (str(SOCIAL_HOME), str(SOCIAL_HOME / "mbm_social")):
        if p not in sys.path:
            sys.path.insert(0, p)


def broadcast(promos=None, brand="cutedosage", gmail=None) -> dict:
    """Generate viral CTA packages for store products and queue for publishing."""
    _flush_imports()
    from high_reach_virality_agent import HighReachViralityAgent

    promos = promos if promos is not None else STORE_PROMOS
    gmail = os.getenv("GMAIL_ACCOUNT") or gmail or "abdelshafyclapps@gmail.com"

    agent = HighReachViralityAgent(brand)
    queue_dir = SOCIAL_HOME / "publish_queue"
    queue_dir.mkdir(parents=True, exist_ok=True)

    queued_files = []
    for promo in promos:
        # HighReach optimizes the base title into a viral package.
        opt = agent.optimize_package_for_maximum_reach(promo["title"], promo.get("niche", "tech"))

        payload = {
            **opt,
            "shopify": {
                "product_id": promo["product_id"],
                "cta_overlay": promo["cta"],
                "store_url": promo["store_url"],
            },
            "gmail_account": gmail,
            "channel_targets": ["tiktok", "youtube_shorts", "instagram_reels"],
            "status": "SHOPIFY_PROMO_QUEUED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        out_file = queue_dir / f"shopify_promo_{brand}_{int(time.time() * 1000)}.json"
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        queued_files.append(str(out_file))
        print(f"[SHOPIFY SOCIAL] Queued '{promo['product_id']}' CTA -> {out_file.name}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brand": brand,
        "queued_count": len(queued_files),
        "queued_files": queued_files,
    }
    LOG_DIR.joinpath("shopify_social_broadcaster_log.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return {
        "status": "success",
        "inputs": {"brand": brand, "promos": len(promos)},
        "outputs": report,
        "errors": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    res = broadcast()
    print(json.dumps(res, indent=2))