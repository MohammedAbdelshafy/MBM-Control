#!/usr/bin/env python3
"""
DIGITAL SERVICES OFFER CATALOG + RECOMMENDATION ENGINE
=======================================================
Canonical pricing for the DIGITAL_SERVICES sales lane. Single source of truth
for every offer (SKU, setup price, monthly maintenance price, category, and
Neteller checkout rail).

Offers (all Neteller checkout, USD):
    - $29  Quick Website     + $9/mo
    - $49  Business Website  + $19/mo
    - $99  Pro Website       + $29/mo
    - $149 Mini App          + $39/mo
    - $249 Business App      + $49/mo

Every offer always carries a monthly maintenance upsell (the maintenance price
is attached to each offer and is surfaced as MAINTENANCE_UPSELL).

Recommendation rules (strongest intent signal chooses the offer):
    - WEBSITE intent            -> $29 Quick Website
    - REPLATFORM / RESPONSIVE   -> $49/$99 website
    - MOBILE_APP intent         -> $149/$249 app
    - ECOMMERCE intent          -> $99 website or $249 app
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from MBM.Scripts.neteller_config import neteller_link
except Exception:
    def neteller_link(amount, item, currency="USD", **kw):
        import urllib.parse
        return (f"https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com"
                f"&account=4599228811&amount={float(amount):.2f}&currency={currency}"
                f"&item={urllib.parse.quote_plus(str(item))}")

CATEGORY_WEBSITE = "WEBSITE"
CATEGORY_APP = "APP"
CATEGORY_MAINTENANCE = "MAINTENANCE_UPSELL"

# Canonical offer catalog — single source of truth.
OFFER_CATALOG = {
    "$29 Quick Website": {
        "sku": "DS-QUICK-WEBSITE",
        "name": "$29 Quick Website",
        "category": CATEGORY_WEBSITE,
        "setup_price": 29,
        "maintenance_price": 9,
        "maintenance_upsell": True,
    },
    "$49 Business Website": {
        "sku": "DS-BUSINESS-WEBSITE",
        "name": "$49 Business Website",
        "category": CATEGORY_WEBSITE,
        "setup_price": 49,
        "maintenance_price": 19,
        "maintenance_upsell": True,
    },
    "$99 Pro Website": {
        "sku": "DS-PRO-WEBSITE",
        "name": "$99 Pro Website",
        "category": CATEGORY_WEBSITE,
        "setup_price": 99,
        "maintenance_price": 29,
        "maintenance_upsell": True,
    },
    "$149 Mini App": {
        "sku": "DS-MINI-APP",
        "name": "$149 Mini App",
        "category": CATEGORY_APP,
        "setup_price": 149,
        "maintenance_price": 39,
        "maintenance_upsell": True,
    },
    "$249 Business App": {
        "sku": "DS-BUSINESS-APP",
        "name": "$249 Business App",
        "category": CATEGORY_APP,
        "setup_price": 249,
        "maintenance_price": 49,
        "maintenance_upsell": True,
    },
}

OFFER_ORDER = [
    "$29 Quick Website",
    "$49 Business Website",
    "$99 Pro Website",
    "$149 Mini App",
    "$249 Business App",
]


def get_offer(name: str) -> Dict[str, Any]:
    """Return a canonical offer dict with the Neteller checkout link attached."""
    offer = dict(OFFER_CATALOG[name])
    offer["neteller_link"] = neteller_link(
        amount=offer["setup_price"],
        item=offer["sku"],
    )
    offer["maintenance_link"] = neteller_link(
        amount=offer["maintenance_price"],
        item=f"{offer['sku']}-MAINT",
    )
    return offer


def recommend_offer(topics: Dict[str, Any], intent_score: int) -> Dict[str, Any]:
    """Choose the canonical offer from the strongest intent signal.

    Deterministic, rule-based:
      - MOBILE_APP strong   -> $149/$249 app
      - ECOMMERCE strong    -> $99 website or $249 app
      - REPLATFORM strong   -> $49/$99 website
      - RESPONSIVE strong   -> $49/$99 website
      - WEBSITE_DESIGN only -> $29 quick website
    The maintenance upsell is ALWAYS attached.
    """
    mobile_app = int(topics.get("MOBILE_APP") or 0)
    ecommerce = int(topics.get("ECOMMERCE") or 0)
    replatform = int(topics.get("REPLATFORM") or 0)
    responsive = int(topics.get("RESPONSIVE_WEB") or 0)
    website_design = int(topics.get("WEBSITE_DESIGN") or 0)

    # Rule 1 — NO real web presence at all (placeholder/free hosting/no domain):
    # the sale is building their first site. Entry offer first, never an app.
    if website_design >= 90:
        name = "$29 Quick Website"
    elif mobile_app >= 80:
        name = "$249 Business App" if (mobile_app >= 90 or ecommerce >= 70) else "$149 Mini App"
    elif ecommerce >= 80:
        name = "$249 Business App" if intent_score >= 80 else "$99 Pro Website"
    elif replatform >= 70 or responsive >= 70:
        name = "$99 Pro Website" if (intent_score >= 75 or website_design >= 60) else "$49 Business Website"
    else:
        # Default for a business with a live (mediocre) domain: Business Website.
        name = "$49 Business Website"

    return get_offer(name)


def offer_rank(name: str) -> int:
    """Stable rank used for offer-fit ordering (higher = stronger offer)."""
    try:
        return OFFER_ORDER.index(name) + 1
    except ValueError:
        return 0


if __name__ == "__main__":
    for n in OFFER_ORDER:
        o = get_offer(n)
        print(f"{o['name']:<22} ${o['setup_price']:>4} setup + ${o['maintenance_price']}/mo | {o['sku']}")