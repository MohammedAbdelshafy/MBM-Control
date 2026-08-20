#!/usr/bin/env python3
"""
DIGITAL SERVICES SALES SCRIPTS
================================
Canonical 8-script pack for the DIGITAL_SERVICES sales lane.

1. 15-Sec Opener
2. Website Pitch
3. App Pitch
4. $29 Close
5. Maintenance Upsell
6. "Already Have a Website"
7. "Too Expensive"
8. "Send Me Something"

Each script is parameterized by {company}, {location}, {domain}, {offer} and the
canonical Neteller checkout link for that offer. Scripts are rendered into every
lead's `scripts` block so the dialer UI shows the right script per lead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.digital_services_offers import get_offer


def _fmt_usd(value) -> str:
    try:
        return f"${int(value)}"
    except Exception:
        return str(value)


def _names(offer: Dict[str, Any]) -> Dict[str, str]:
    setup = _fmt_usd(offer["setup_price"])
    monthly = _fmt_usd(offer["maintenance_price"])
    return {"setup": setup, "monthly": monthly, "offer": offer["name"], "sku": offer["sku"]}


def _pay(offer: Dict[str, Any], what: str = "") -> str:
    return offer["neteller_link"]


def build_scripts(company: str, location: str, domain: str, offer: Dict[str, Any]) -> Dict[str, Any]:
    """Render the full 8-script pack for one lead."""
    n = _names(offer)
    co = company or "your company"
    loc = location or "your area"
    dom = domain or "your website"

    return {
        "opener_15s": (
            f"Hi, is this {co} in {loc}? Quick one — I build websites for "
            f"businesses like yours that don't have one or have an old one. "
            f"Could I send you a one-line sample? I won't take more than 20 seconds."
        ),
        "website_pitch": (
            f"We build {co} a professional website for {n['setup']} plus "
            f"{n['monthly']}/month, all-in — design, hosting, updates, and "
            f"maintenance. No hidden costs, and you own everything. "
            f"Want me to sketch what {dom} would look like?"
        ),
        "app_pitch": (
            f"For {co}, I'd recommend turning what you do into a mini app — "
            f"{n['setup']} to launch, {n['monthly']}/month to run. Clients can "
            f"book, buy, or reach you from their phone. It's the fastest way to "
            f"look bigger than you are."
        ),
        "close_29": (
            f"Today I can get {co} online with a professional one-page site for "
            f"just {n['setup']} and {n['monthly']}/month — that's it. Checkout "
            f"is two minutes on Neteller, and I start today. "
            f"Ready to lock that in?"
        ),
        "maintenance_upsell": (
            f"Every build I do includes {n['monthly']}/month care — hosting, "
            f"backups, security updates, and small edits whenever you ask. "
            f"You'll never be stuck with a broken site or have to learn code. "
            f"Most owners tell me that alone is worth it."
        ),
        "already_have_website": (
            f"Got it — if {co} already has a site, my job is to make it convert. "
            f"I'll run a free 5-point audit of {dom} (speed, mobile, Google "
            f"visibility, trust, checkout) and send you a plain-English list of "
            f"the 3 fixes that would bring the most clients. Fair?"
        ),
        "too_expensive": (
            f"I hear you. The {n['setup']} option is the leanest way in, and "
            f"it's month-to-month — no contract. If it doesn't earn that back "
            f"in one client, I'll cancel you out myself. "
            f"How does {co} usually find new customers today?"
        ),
        "send_something": (
            f"Perfect — I'll send over a one-page proposal for {co}: what I'd "
            f"build, the {n['setup']} + {n['monthly']}/month pricing, and a "
            f"live example. No follow-up spam, I promise. "
            f"What's the best email for it?"
        ),
    }


def build_digital_script_pack(company: str, location: str, domain: str, offer: Dict[str, Any]) -> Dict[str, Any]:
    """Public helper: return scripts + checkout payload for a lead."""
    return {
        "pack": "DIGITAL_SERVICES",
        "scripts": build_scripts(company, location, domain, offer),
        "checkout": {
            "setup_price": offer["setup_price"],
            "maintenance_price": offer["maintenance_price"],
            "neteller_link": offer["neteller_link"],
            "sku": offer["sku"],
        },
    }


if __name__ == "__main__":
    offer = get_offer("$49 Business Website")
    pack = build_digital_script_pack("Acme Landscaping", "Dallas, TX", "acmelandscaping.com", offer)
    for key, text in pack["scripts"].items():
        print(f"--- {key} ---")
        print(text)
        print()