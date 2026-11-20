"""Environment-backed Neteller checkout-link construction.

Wallet identity is deliberately never committed to source control. Runtime
payment links require explicit NETELLER_EMAIL and NETELLER_ACCOUNT_ID values.
"""

import math
import os
import re
from typing import Optional
from urllib.parse import urlencode, urlparse

NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "").strip()
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "").strip()
NETELLER_PAY_BASE = os.getenv(
    "NETELLER_PAY_BASE",
    "https://member.neteller.com/pay",
).strip()


def neteller_link(
    amount: float,
    item: str,
    currency: str = "USD",
    email: Optional[str] = None,
    account: Optional[str] = None,
    base: Optional[str] = None,
) -> str:
    """Build a Neteller member-pay URL using explicit or environment settings.

    The function does not infer a wallet identity. Applications should only
    call it after their own quote and checkout approval gates have passed.
    """
    try:
        normalized_amount = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("amount must be a finite non-negative number") from exc
    if not math.isfinite(normalized_amount) or normalized_amount < 0:
        raise ValueError("amount must be a finite non-negative number")

    normalized_item = str(item or "").strip()
    if not normalized_item:
        raise ValueError("item is required")

    normalized_currency = str(currency or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
        raise ValueError("currency must be a three-letter ISO 4217 code")

    resolved_email = str(email or NETELLER_EMAIL).strip()
    resolved_account = str(account or NETELLER_ACCOUNT_ID).strip()
    if not resolved_email or not resolved_account:
        raise RuntimeError(
            "NETELLER_EMAIL and NETELLER_ACCOUNT_ID must be explicitly configured"
        )
    if "@" not in resolved_email or any(char.isspace() for char in resolved_email):
        raise ValueError("NETELLER_EMAIL must be a valid email address")

    resolved_base = str(base or NETELLER_PAY_BASE).strip()
    parsed_base = urlparse(resolved_base)
    if parsed_base.scheme != "https" or not parsed_base.netloc:
        raise ValueError("NETELLER_PAY_BASE must be an HTTPS URL")

    params = urlencode(
        {
            "email": resolved_email,
            "account": resolved_account,
            "amount": f"{normalized_amount:.2f}",
            "currency": normalized_currency,
            "item": normalized_item,
        }
    )
    separator = "&" if parsed_base.query else "?"
    return f"{resolved_base}{separator}{params}"


def neteller_wallet_label() -> str:
    """Return a safe status label without exposing wallet details."""
    if not NETELLER_EMAIL or not NETELLER_ACCOUNT_ID:
        return "Neteller wallet not configured"
    return "Neteller wallet configured"


if __name__ == "__main__":
    print(neteller_wallet_label())
