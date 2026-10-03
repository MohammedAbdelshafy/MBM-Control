#!/usr/bin/env python3
"""
MBM Lead Cleaner — MCP Server
============================
Exposes MBM's lead verification engine as MCP tools for agent ecosystems.

Tools:
  clean_leads      — Clean, verify, dedupe, and score a lead list (CSV input)
  score_lead       — Score a single lead (0-100)
  verify_email     — Validate an email address (syntax + deliverability signals)
  generate_outreach— Generate a personalized cold outreach email for a lead

Distribution targets: MCP Registry, Smithery, Glama, Hugging Face, LobeHub.
Part of the MBM Agent Package (Lead Cleaner = first commercial package).
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mbm-lead-cleaner")


# ---------------------------------------------------------------------------
# Core engine (self-contained port of MBM-Control's verification logic)
# ---------------------------------------------------------------------------

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "throwaway.email", "fakeinbox.com", "trashmail.com", "yopmail.com",
}
FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "protonmail.com",
}
ROLE_PREFIXES = {"info", "support", "sales", "admin", "contact", "hello", "help"}


def _digits(phone: Any) -> str:
    return re.sub(r"\D", "", str(phone or ""))


def _normalize_phone(phone: Any) -> str:
    d = _digits(phone)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _classify_phone(phone: Any) -> tuple[str, str]:
    """Returns (status, reason)."""
    raw = str(phone or "").strip()
    if not raw:
        return "MISSING", "no phone provided"
    d = _digits(raw)
    if len(d) < 7:
        return "INVALID", "too few digits"
    if re.fullmatch(r"(\d)\1{6,}", d):
        return "INVALID", "repeated-digit pattern"
    if len(d) in (7, 10) or (len(d) == 11 and d.startswith("1")):
        return "CALLABLE", "valid NANP format"
    return "NEEDS REVIEW", "unusual format"


def _classify_email(email: Any) -> tuple[str, str]:
    raw = str(email or "").strip().lower()
    if not raw:
        return "MISSING", "no email provided"
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", raw):
        return "INVALID", "fails syntax check"
    domain = raw.split("@", 1)[1]
    if domain in DISPOSABLE_DOMAINS:
        return "RISKY", "disposable domain"
    local = raw.split("@", 1)[0]
    if local in ROLE_PREFIXES:
        return "ROLE", "role-based address (lower reply rate)"
    if domain in FREE_DOMAINS:
        return "VALID_FREE", "valid syntax, free provider"
    return "VALID_WORK", "valid syntax, business domain"


def _score_lead(row: dict) -> tuple[int, list[str]]:
    score = 0
    notes: list[str] = []

    phone_status, phone_reason = _classify_phone(row.get("phone", ""))
    email_status, email_reason = _classify_email(row.get("email", ""))
    name = str(row.get("name", "") or row.get("contact_name", "")).strip()

    if phone_status == "CALLABLE":
        score += 35
    elif phone_status == "NEEDS REVIEW":
        score += 15
        notes.append(f"phone: {phone_reason}")
    else:
        notes.append(f"phone {phone_status.lower()}: {phone_reason}")

    if email_status == "VALID_WORK":
        score += 35
    elif email_status == "VALID_FREE":
        score += 25
    elif email_status == "ROLE":
        score += 15
        notes.append("role-based email")
    else:
        notes.append(f"email {email_status.lower()}: {email_reason}")

    if len(name.split()) >= 2:
        score += 15
    elif name:
        score += 8
        notes.append("single-name contact")
    else:
        notes.append("no contact name")

    if row.get("company"):
        score += 15
    else:
        notes.append("no company")

    return min(score, 100), notes


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def clean_leads(csv_text: str) -> str:
    """Clean, verify, dedupe, and score a lead list.

    Args:
        csv_text: CSV content with headers. Recognized columns: name/contact_name,
            email, phone/phone_number, company/company_name.

    Returns:
        JSON with cleaned leads (each scored 0-100 with status), summary stats,
        and a human-readable report.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    total = len(rows)

    seen_phones: set[str] = set()
    seen_emails: set[str] = set()
    cleaned: list[dict] = []
    counts: dict[str, int] = {}

    for row in rows:
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        get = lambda *keys: next((norm[k] for k in keys if norm.get(k)), "")

        lead = {
            "name": get("name", "contact_name", "contact", "full_name"),
            "email": get("email", "email_address", "e-mail"),
            "phone": get("phone", "phone_number", "phone1", "mobile"),
            "company": get("company", "company_name", "business", "organization"),
        }

        phone_norm = _normalize_phone(lead["phone"])
        email_norm = lead["email"].lower()
        if phone_norm and phone_norm in seen_phones:
            lead["status"] = "DUPLICATE"
            lead["reason"] = "duplicate phone"
        elif email_norm and email_norm in seen_emails:
            lead["status"] = "DUPLICATE"
            lead["reason"] = "duplicate email"
        else:
            score, notes = _score_lead(lead)
            lead["score"] = score
            lead["notes"] = notes
            lead["status"] = (
                "VERIFIED" if score >= 70 else
                "CALLABLE" if score >= 45 else
                "NEEDS REVIEW" if score >= 25 else
                "NOT CALLABLE"
            )
            lead["reason"] = "; ".join(notes) if notes else "all signals strong"
        if phone_norm:
            seen_phones.add(phone_norm)
        if email_norm:
            seen_emails.add(email_norm)

        counts[lead["status"]] = counts.get(lead["status"], 0) + 1
        cleaned.append(lead)

    verified = counts.get("VERIFIED", 0) + counts.get("CALLABLE", 0)
    report = (
        f"Processed {total} leads: {verified} callable "
        f"({counts.get('VERIFIED', 0)} verified), "
        f"{counts.get('DUPLICATE', 0)} duplicates removed, "
        f"{counts.get('NOT CALLABLE', 0)} not callable, "
        f"{counts.get('NEEDS REVIEW', 0)} need review."
    )
    return json.dumps({"leads": cleaned, "summary": counts, "report": report}, indent=2)


@mcp.tool()
def score_lead(name: str = "", email: str = "", phone: str = "", company: str = "") -> str:
    """Score a single lead 0-100 with a breakdown.

    Returns JSON: {score, status, signals: {phone, email}, notes}.
    """
    lead = {"name": name, "email": email, "phone": phone, "company": company}
    score, notes = _score_lead(lead)
    phone_status, _ = _classify_phone(phone)
    email_status, _ = _classify_email(email)
    return json.dumps({
        "score": score,
        "status": "VERIFIED" if score >= 70 else "CALLABLE" if score >= 45
                  else "NEEDS REVIEW" if score >= 25 else "NOT CALLABLE",
        "signals": {"phone": phone_status, "email": email_status},
        "notes": notes,
    }, indent=2)


@mcp.tool()
def verify_email(email: str) -> str:
    """Deep-check a single email address. Returns JSON with status and reasoning."""
    status, reason = _classify_email(email)
    return json.dumps({"email": email.strip().lower(), "status": status, "reason": reason}, indent=2)


@mcp.tool()
def generate_outreach(name: str, company: str, pain_point: str = "messy lead lists",
                      offer: str = "a free 50-lead sample clean") -> str:
    """Generate a personalized cold outreach email for a lead.

    Returns JSON with subject options and email body.
    """
    first = (name or "there").split()[0]
    subjects = [
        f"{first}, your lead list cleaned in 48 hours",
        f"quick idea for {company or 'your team'}",
        f"{first} — stop calling dead numbers",
    ]
    body = (
        f"Hi {first},\n\n"
        f"Noticed {company or 'your company'} is growing — congrats.\n\n"
        f"Most teams we talk to lose 20-30% of their dial time to {pain_point}: "
        f"disconnected numbers, fake emails, duplicates.\n\n"
        f"We clean and verify lead lists in 48 hours — every number checked, "
        f"every email validated, scored 0-100 so your team calls the best first.\n\n"
        f"Happy to do {offer} so you can see the before/after on your own data. "
        f"No strings.\n\n"
        f"Worth a look?\n\n"
        f"Best,\nMohammed"
    )
    return json.dumps({"subjects": subjects, "body": body}, indent=2)


if __name__ == "__main__":
    mcp.run()
