"""
dedup.py — deterministic canonical-domain + dedup for TargetAccount (Phase 2).

Mirrors spec-ad-engine/src/targetAccount/dedup.js behavior in Python,
with no invented domains. Reuses no LeadEngine internals except for
provenance handling via plain dicts.

Requirements (Step 3):
- lowercase, remove protocol, remove www., remove port, remove path/query/fragment,
  reject malformed, reject placeholder/example domains, preserve meaningful subdomains
  (only www. is stripped), do not invent domains from company names.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_PLACEHOLDER_DOMAINS = {"example.com", "test.com", "example.org"}

# keep deterministic: no PSL, only strip leading www.
_valid_label_re = re.compile(r"^[a-z0-9-]+$")


def canonicalize_domain(raw: Any) -> str | None:
    """Return canonical domain or None if not extractable / invalid."""
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s:
        return None

    # email → domain extraction (only if not a URL)
    if "@" in s and "/" not in s and " " not in s:
        at = s.rfind("@")
        s = s[at + 1 :]

    # strip protocol
    if s.startswith("https://"):
        s = s[len("https://") :]
    elif s.startswith("http://"):
        s = s[len("http://") :]
    elif s.startswith("//"):
        s = s[2:]

    # host only (before /, ?, #)
    for sep in ("/", "?", "#"):
        idx = s.find(sep)
        if idx != -1:
            s = s[:idx]

    # strip port
    if ":" in s:
        # only trailing :digits is considered port
        if re.search(r":\d+$", s):
            s = s[: s.rfind(":")]

    # strip leading www.
    if s.startswith("www."):
        s = s[4:]

    # strip trailing dot
    if s.endswith("."):
        s = s[:-1]

    if "." not in s:
        return None
    if s in _PLACEHOLDER_DOMAINS:
        return None
    if " " in s:
        return None
    if not re.fullmatch(r"[a-z0-9.-]+", s):
        return None
    if s.startswith("-") or s.endswith("-") or s.startswith(".") or s.endswith("."):
        return None
    labels = s.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return None
        if not _valid_label_re.fullmatch(label):
            return None
        if label.startswith("-") or label.endswith("-"):
            return None
    if len(s) > 253:
        return None
    return s


def extract_canonical_domain(account: Dict[str, Any] | None) -> str | None:
    if not isinstance(account, dict):
        return None
    candidates = [
        account.get("canonical_domain"),
        account.get("canonicalDomain"),
        account.get("domain"),
        account.get("website"),
        account.get("url"),
        account.get("company_website"),
        account.get("companyWebsite"),
    ]
    for c in candidates:
        canon = canonicalize_domain(c) if isinstance(c, str) else None
        if canon:
            return canon
    email = account.get("email") or account.get("contact_email") or account.get("company_email")
    if isinstance(email, str) and email:
        canon = canonicalize_domain(email)
        if canon:
            return canon
    return None


def dedup_key(account: Dict[str, Any] | None) -> str | None:
    """Deterministic idempotency key. Strongest: domain → normalized company_name → id."""
    if not isinstance(account, dict):
        return None
    domain = extract_canonical_domain(account)
    if domain:
        return f"domain:{domain}"
    name = str(account.get("company_name") or account.get("companyName") or account.get("company") or "").strip().lower()
    if name:
        norm = re.sub(r"[^a-z0-9]+", "-", name).strip("-")[:80]
        if norm:
            return f"name:{norm}"
    ident = str(account.get("id") or "").strip()
    if ident:
        return f"id:{ident}"
    return None


def is_duplicate(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ka = dedup_key(a)
    kb = dedup_key(b)
    if not ka or not kb:
        return False
    return ka == kb


def dedup_accounts(accounts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Keep first occurrence (deterministic). Returns (unique, duplicates)."""
    seen: Dict[str, Dict[str, Any]] = {}
    unique: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    for acc in accounts:
        key = dedup_key(acc)
        if not key:
            unique.append(acc)
            continue
        if key in seen:
            duplicates.append(acc)
        else:
            seen[key] = acc
            unique.append(acc)
    return unique, duplicates


def detect_conflicting_identity(
    existing: Dict[str, Any], incoming: Dict[str, Any]
) -> bool:
    """
    True if two records share a domain but have materially conflicting identities.
    Used to avoid silent overwrite: if conflict, caller must mark, not merge.
    """
    d_existing = extract_canonical_domain(existing)
    d_incoming = extract_canonical_domain(incoming)
    if not d_existing or not d_incoming or d_existing != d_incoming:
        return False
    name_e = str(existing.get("company_name") or existing.get("companyName") or existing.get("company") or "").strip().lower()
    name_i = str(incoming.get("company_name") or incoming.get("companyName") or incoming.get("company") or "").strip().lower()
    if not name_e or not name_i:
        return False
    # normalize and compare: if both present but Levenshtein-ish different beyond trivial
    norm_e = re.sub(r"[^a-z0-9]+", "", name_e)
    norm_i = re.sub(r"[^a-z0-9]+", "", name_i)
    # if one is substring of other (e.g., "Acme" vs "Acme Inc") not conflict
    if norm_e in norm_i or norm_i in norm_e:
        return False
    # otherwise if normalized names share < 50% overlap → conflict
    # simple heuristic: if first 4 chars differ and no token overlap
    tokens_e = set(re.findall(r"[a-z0-9]+", name_e))
    tokens_i = set(re.findall(r"[a-z0-9]+", name_i))
    if tokens_e.isdisjoint(tokens_i):
        return True
    return False
