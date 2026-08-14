"""
neteller_config.py — Canonical Neteller payout configuration & pay-link builder
===============================================================================
Single source of truth for every Neteller monetization surface in the repo.

The Neteller "member pay" URL lets a buyer pay directly into the wallet without
a storefront. Every checkout, blaster, hub, landing page, and payout endpoint
must build links through ``neteller_link()`` so wallet details live in exactly
one place.

Defaults (owned account):
    email      = abdelshafyclapps@gmail.com
    account_id = 4599228811

Overridable via env:
    NETELLER_EMAIL
    NETELLER_ACCOUNT_ID
    NETELLER_PAY_BASE

Import as:

    from MBM.Scripts.neteller_config import NETELLER_EMAIL, neteller_link
    url = neteller_link(amount=997.00, item="50_US_Lead_Pack")
"""

import os
from typing import Optional
from urllib.parse import urlencode

NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")
NETELLER_PAY_BASE = os.getenv("NETELLER_PAY_BASE", "https://member.neteller.com/pay")


def neteller_link(
    amount: float,
    item: str,
    currency: str = "USD",
    email: Optional[str] = None,
    account: Optional[str] = None,
    base: Optional[str] = None,
) -> str:
    """Build a 1-click Neteller member-pay URL.

    Args:
        amount:   Decimal amount to charge (e.g. 997.00).
        item:     URL-safe item/sku label shown to the buyer.
        currency: ISO 4217 currency code. Default "USD".
        email:    Override wallet email. Defaults to canonical NETELLER_EMAIL.
        account:  Override wallet account id. Defaults to canonical NETELLER_ACCOUNT_ID.
        base:     Override pay endpoint. Defaults to canonical NETELLER_PAY_BASE.

    Returns:
        Fully-formed Neteller checkout URL.
    """
    email = email or NETELLER_EMAIL
    account = account or NETELLER_ACCOUNT_ID
    base = base or NETELLER_PAY_BASE
    params = urlencode(
        {
            "email": email,
            "account": account,
            "amount": f"{float(amount):.2f}",
            "currency": currency,
            "item": item,
        }
    )
    return f"{base}?{params}"


def neteller_wallet_label() -> str:
    """Human-readable wallet label, e.g. 'abdelshafyclapps@gmail.com (Account: 4599228811)'."""
    return f"{NETELLER_EMAIL} (Account: {NETELLER_ACCOUNT_ID})"


if __name__ == "__main__":
    print(neteller_wallet_label())
    print(neteller_link(amount=997.00, item="50_US_Lead_Pack"))