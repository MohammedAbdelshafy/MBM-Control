"""REAL_ESTATE_AGENT deduplication.

Primary key: normalized professional contact (phone/email).
Secondary: agent+brokerage+domain identity.
Missing data never collides (UNKNOWN-safe, D-019 rail 16).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def normalize_phone(value: Any) -> str:
    d = _digits(value)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def normalize_email(value: Any) -> str:
    e = str(value or "").strip().lower()
    return e if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e) else ""


_FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
              "icloud.com", "aol.com"}


def domain_of(email: str, website: Any = "") -> str:
    dom = ""
    if email and "@" in email:
        d = email.split("@", 1)[1].strip().lower()
        if d not in _FREE_MAIL:
            dom = d
    if not dom:
        w = str(website or "").strip().lower()
        w = re.sub(r"^https?://", "", w).split("/", 1)[0]
        w = w.replace("www.", "")
        dom = w if "." in w else ""
    return dom


def name_norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def dedup_key(agent: Dict[str, Any]) -> Tuple[str, str]:
    """Returns (primary_key, secondary_key); empty string component = no key."""
    phone = normalize_phone(agent.get("phone"))
    email = normalize_email(agent.get("email"))
    primary = f"email:{email}" if email else (f"phone:{phone}" if phone else "")
    # Secondary identity requires >=2 components so bare common names never
    # collide on their own - EXCEPT a company domain, which is a strong
    # company-level identifier on its own.
    comps = [name_norm(agent.get("agent_name")),
             name_norm(agent.get("brokerage")),
             domain_of(email, agent.get("website"))]
    comps = [c for c in comps if c]
    if len(comps) >= 2:
        secondary = f"ident:{'|'.join(comps)}"
    elif len(comps) == 1 and "." in comps[0]:
        secondary = f"ident:{comps[0]}"
    else:
        secondary = ""
    return primary, secondary


def find_duplicate(candidate: Dict[str, Any], existing: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the first duplicate record, or None."""
    c_primary, c_secondary = dedup_key(candidate)
    if not c_primary and not c_secondary:
        return None
    for row in existing:
        r_primary, r_secondary = dedup_key(row)
        if c_primary and c_primary == r_primary:
            return row
        if c_secondary and c_secondary == r_secondary:
            return row
        # same person moved brokerages: email/phone exact match is primary;
        # bare name+brokerage equality alone is NOT enough (common names).
    return None
