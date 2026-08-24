"""validation -- pure, hermetic validators. No network, no I/O."""
from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"\d+")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_phone(raw: str) -> str | None:
    """Return 10-digit NANP string for US numbers, else None.

    Accepts +1 prefixed or bare 10-digit inputs. Rejects anything else
    (non-US country codes, wrong length) rather than guessing.
    """
    if not raw:
        return None
    digits = "".join(_DIGITS_RE.findall(str(raw)))
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return None
    area, exchange, _line = digits[0:3], digits[3:6], digits[6:10]
    if area[0] in ("0", "1") or exchange[0] in ("0", "1"):
        return None
    if area[2:] == "11" or area == "555":
        return None
    return digits


def is_valid_us_phone(raw: str) -> bool:
    return normalize_phone(raw) is not None


_EMAIL_FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "live.com", "msn.com",
}


def is_plausible_email(email: str) -> bool:
    """Syntax check only. Free-domain addresses stay plausible because a
    practice-published gmail address is still a legitimate business route;
    legitimacy is decided by the gate (source + class), not here."""
    if not email or not _EMAIL_RE.match(email):
        return False
    return True


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


def is_free_domain(email: str) -> bool:
    return email_domain(email) in _EMAIL_FREE_DOMAINS


def practice_dedupe_key(name: str, phone: str = "") -> str:
    """Stable duplicate key for practices: normalized phone when present,
    otherwise slug of the name tokens."""
    norm = normalize_phone(phone)
    if norm:
        return f"phone:{norm}"
    slug = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return f"name:{slug}" if slug else "name:unknown"


def contact_dedupe_key(value: str) -> str:
    v = (value or "").strip().lower()
    if "@" in v:
        local, _, domain = v.partition("@")
        local = local.split("+", 1)[0]
        return f"email:{local}@{domain}"
    norm = normalize_phone(v)
    if norm:
        return f"phone:{norm}"
    return f"raw:{re.sub(r'[^a-z0-9]+', '', v)}"
