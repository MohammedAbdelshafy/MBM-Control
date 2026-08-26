"""Shared fakes/fixtures for the Real Estate AI Media vertical tests.

Hermetic: no Frappe runtime, no network, no real renders.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
for _p in (APP.parent, APP):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pytest  # noqa: E402


@pytest.fixture()
def now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def good_agent():
    return {
        "agent_id": "AG-1",
        "agent_name": "Dana Whitfield",
        "brokerage": "Summit Realty",
        "email": "dana@summitrealty.com",
        "phone": "+1 512 555 0142",
        "website": "https://summitrealty.com",
        "market": "Austin, TX",
        "market_median_price": 550000,
        "active_listings": 6,
        "listings_last_90d": 4,
        "presentation_quality": "POOR",
        "has_video": False,
        "social_followers": 12000,
        "brokerage_agent_count": 60,
        "high_turnover_market": True,
    }


def make_history(*states, start=None, gap_hours=24):
    start = start or datetime.now(timezone.utc) - timedelta(days=30)
    out = []
    t = start
    for s in states:
        out.append({"state": s, "at": t})
        t += timedelta(hours=gap_hours)
    return out
