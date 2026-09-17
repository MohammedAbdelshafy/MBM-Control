""" wrapped MBM capabilities on the MCP bus (P0.5 / Part I).

Exposes MATURE specialists as callable capabilities. Zero duplicated
logic — every handler delegates to the existing canonical implementation:

    dialer_eligibility_filter -> MBM.LeadEngine.dialer_verification_gate.filter_for_dialer
    suppression_check         -> MBM/Artifacts/suppressed_bad_phones.json (canonical dict
                                 schema) + suppression_list.json (email)
    phound_status             -> MBM.LeadEngine.phound_provider.get_provider_status (UI-safe)
    phound_dry_run_call       -> PhoundProvider.place_call(dry_run=True) AFTER gate +
                                 suppression + policy checks (defense in depth)
    browser_navigate_extract  -> read-only page-text extraction constrained to
                                 BROWSER_ALLOWED_DOMAINS (mirrors
                                 MBM/Scripts/adapters/playwright_adapter.py:
                                 PlaywrightAdapter.ALLOWED_DOMAINS)

Safety: `phound_dry_run_call` HARD-CODES dry_run=True. There is deliberately
NO live-call capability — live placement stays behind the CLI/human approval
path. Every mutating intent re-evaluates policy at call time.
`browser_navigate_extract` is READ-only: exact/suffix hostname allowlist,
http/https only, no writes, no credentials.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .mcp_a2a import MCPToolBus, MCPToolDefinition
from .policy import ActionClass, evaluate, PolicyVerdict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPPRESSION_FILE = ROOT / "MBM" / "Artifacts" / "suppressed_bad_phones.json"
DEFAULT_EMAIL_SUPPRESSION_FILE = ROOT / "suppression_list.json"


def _require_args(args: Mapping[str, Any], required: List[str], tool: str) -> None:
    for key in required:
        if key not in args:
            raise ValueError(f"tool {tool}: missing required input '{key}'")


# -- capability 1: dialer eligibility -------------------------------------------
def dialer_eligibility_filter(args: Mapping[str, Any]) -> Dict[str, Any]:
    """Filter raw leads through the canonical verification gate."""
    from MBM.LeadEngine.dialer_verification_gate import filter_for_dialer

    _require_args(args, ["leads"], "dialer_eligibility_filter")
    leads = args["leads"]
    if not isinstance(leads, list) or not all(isinstance(l, dict) for l in leads):
        raise ValueError("tool dialer_eligibility_filter: 'leads' must be a list of objects")
    eligible = filter_for_dialer([dict(l) for l in leads], quiet=True)
    eligible_ids = {str(l.get("id")) for l in eligible}
    return {
        "eligible": eligible,
        "eligible_count": len(eligible),
        "blocked_count": len(leads) - len(eligible),
        "blocked_ids": [str(l.get("id")) for l in leads if str(l.get("id")) not in eligible_ids],
    }


# -- capability 2: suppression ----------------------------------------------------
def _load_phone_suppression(path: Path) -> set:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, dict):
        data = data.get("suppressed_phones", [])
    if not isinstance(data, list):
        return set()
    import re

    out = set()
    for p in data:
        digits = re.sub(r"\D", "", str(p))
        if digits:
            out.add(digits[-10:] if len(digits) >= 10 else digits)
    return out


def suppression_check(args: Mapping[str, Any], suppression_file: Optional[Path] = None) -> Dict[str, Any]:
    """Read-only suppression verdict for one phone and/or email."""
    import re

    _require_args(args, [], "suppression_check")
    phone = str(args.get("phone") or "")
    email = str(args.get("email") or "").strip().lower()
    if not phone and not email:
        raise ValueError("tool suppression_check: provide 'phone' and/or 'email'")
    reasons: List[str] = []
    if phone:
        digits = re.sub(r"\D", "", phone)
        norm = digits[-10:] if len(digits) >= 10 else digits
        if norm and norm in _load_phone_suppression(suppression_file or DEFAULT_SUPPRESSION_FILE):
            reasons.append("phone_suppressed_bad_phones_index")
    if email:
        try:
            suppressed = json.loads(DEFAULT_EMAIL_SUPPRESSION_FILE.read_text(encoding="utf-8"))
            if email in {str(e).strip().lower() for e in (suppressed if isinstance(suppressed, list) else [])}:
                reasons.append("email_suppressed_opt_out")
        except Exception:
            pass
    return {"suppressed": bool(reasons), "reasons": reasons, "phone": phone, "email": email}


# -- capability 3/4: phound ---------------------------------------------------------
def phound_status(args: Mapping[str, Any], env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """UI-safe provider status. Never exposes credentials (upstream redacts)."""
    from MBM.LeadEngine.phound_provider import get_provider_status

    return get_provider_status(dict(env or os.environ))


def phound_dry_run_call(
    args: Mapping[str, Any],
    env: Optional[Mapping[str, str]] = None,
    suppression_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Resolve + gate + simulate a call. DRY RUN ONLY — dry_run is hard-coded True.

    Gate chain (all must pass): verification gate -> suppression check ->
    policy approval (REQUIRE_APPROVAL satisfies planning; DENY refuses).
    """
    from MBM.LeadEngine.phound_provider import PhoundProvider

    _require_args(args, ["lead_id", "phone", "persona_uid"], "phound_dry_run_call")
    lead = {"id": args["lead_id"], "phone": args["phone"], "name": args.get("name", "Capability Check")}
    for extra in ("skip_trace_status", "verification_status", "source"):
        if extra in args:
            lead[extra] = args[extra]

    from MBM.LeadEngine.dialer_verification_gate import filter_for_dialer

    if not filter_for_dialer([lead], quiet=True):
        return {"status": "gate_blocked", "reason": "dialer_verification_gate", "lead_id": args["lead_id"]}

    sup = suppression_check({"phone": args["phone"]}, suppression_file)
    if sup["suppressed"]:
        return {"status": "gate_blocked", "reason": sup["reasons"], "lead_id": args["lead_id"]}

    decision = evaluate(
        f"place real call via provider bridge for lead {args['lead_id']}",
        approval=args.get("approval"),
    )
    if decision.verdict is PolicyVerdict.DENY:
        return {"status": "policy_denied", "reason": decision.reason, "lead_id": args["lead_id"]}

    provider = PhoundProvider(env=dict(env or os.environ))
    result = provider.place_call(
        lead_id=str(args["lead_id"]),
        phone=str(args["phone"]),
        persona_uid=str(args["persona_uid"]),
        request_id=args.get("request_id"),
        dry_run=True,  # HARD SAFETY: this capability can never place a live call
    )
    result["policy"] = decision.verdict.value
    return result


# -- capability 5: browser automation (Playwright, read-only) -------------------
# Allowlist MUST mirror MBM/Scripts/adapters/playwright_adapter.py
# PlaywrightAdapter.ALLOWED_DOMAINS (asserted by test_browser_automation.py).
BROWSER_ALLOWED_DOMAINS = ["example.com", "github.com", "zillow.com"]
BROWSER_MAX_URL_LENGTH = 2048
BROWSER_MAX_CONTENT_CHARS = 20000
BROWSER_TIMEOUT_SEC = 30


def _browser_enforce_whitelist(url: Any) -> str:
    """Validate URL shape and allowlist. Returns the lowercase hostname."""
    from urllib.parse import urlparse

    if not isinstance(url, str) or not url:
        raise ValueError("tool browser_navigate_extract: 'url' must be a non-empty string")
    if len(url) > BROWSER_MAX_URL_LENGTH:
        raise ValueError(
            f"tool browser_navigate_extract: 'url' exceeds {BROWSER_MAX_URL_LENGTH} chars"
        )
    if any(c in url for c in (" ", "\t", "\n", "\r", "\x00")):
        raise ValueError("tool browser_navigate_extract: 'url' contains whitespace/control characters")
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"tool browser_navigate_extract: malformed url: {exc}") from exc
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("tool browser_navigate_extract: only http/https urls are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("tool browser_navigate_extract: url has no hostname")
    if not any(host == d or host.endswith("." + d) for d in BROWSER_ALLOWED_DOMAINS):
        raise PermissionError(
            f"tool browser_navigate_extract: host '{host}' is not in the allowed domains list."
        )
    return host


def _browser_playwright_fetch(url: str) -> str:
    """Production fetch via Playwright. Imported lazily so tests need no browser."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "playwright is not installed; `pip install playwright` + "
            "`playwright install chromium`, or inject browser_fetcher"
        ) from exc
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=BROWSER_TIMEOUT_SEC * 1000)
            try:
                return page.inner_text("body")
            except Exception:
                return page.content()
        finally:
            browser.close()


def browser_navigate_extract(args: Mapping[str, Any], browser_fetcher=None) -> Dict[str, Any]:
    """Extract page text from an allowlisted URL. READ-only; no writes, no creds."""
    _require_args(args, ["url"], "browser_navigate_extract")
    url = args["url"]
    host = _browser_enforce_whitelist(url)
    fetch = browser_fetcher or _browser_playwright_fetch
    try:
        content = fetch(url)
    except (PermissionError, ValueError):
        raise
    except Exception as exc:
        msg = str(exc).lower()
        kind = "timeout" if "timeout" in msg or "timed out" in msg else "provider_unavailable"
        wrapped = RuntimeError(str(exc)[:500])
        setattr(wrapped, "error_kind", kind)
        raise wrapped from exc
    if not isinstance(content, str):
        content = str(content)
    truncated = len(content) > BROWSER_MAX_CONTENT_CHARS
    return {
        "status": "success",
        "url": url,
        "host": host,
        "content": content[:BROWSER_MAX_CONTENT_CHARS],
        "content_length": len(content),
        "truncated": truncated,
    }


def build_capability_bus(
    suppression_file: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    browser_fetcher=None,
) -> MCPToolBus:
    """Register the wrapped capabilities on a filtered MCP bus.

    ``browser_fetcher`` is an injectable ``(url) -> str`` callable used by
    ``browser_navigate_extract``. Production leaves it ``None`` (lazy
    Playwright import at call time); tests inject a stub so the suite stays
    hermetic with no network or browser.
    """
    bus = MCPToolBus()
    bus.register(MCPToolDefinition(
        name="dialer_eligibility_filter",
        description="Filter raw leads through the canonical dialer verification gate. Read-only.",
        input_schema={"type": "object", "required": ["leads"], "properties": {"leads": {"type": "array"}}},
        handler=dialer_eligibility_filter,
        action_class=ActionClass.READ,
    ))
    bus.register(MCPToolDefinition(
        name="suppression_check",
        description="Read-only DNC/suppression verdict for a phone and/or email.",
        input_schema={"type": "object", "required": [], "properties": {"phone": {"type": "string"}, "email": {"type": "string"}}},
        handler=lambda a: suppression_check(a, suppression_file),
        action_class=ActionClass.READ,
    ))
    bus.register(MCPToolDefinition(
        name="phound_status",
        description="UI-safe Phound provider status. No credentials exposed.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: phound_status(a, env),
        action_class=ActionClass.READ,
    ))
    bus.register(MCPToolDefinition(
        name="phound_dry_run_call",
        description="Gate + simulate a call via PhoundProvider. DRY RUN ONLY; hard-coded dry_run=True.",
        input_schema={"type": "object", "required": ["lead_id", "phone", "persona_uid"],
                      "properties": {"lead_id": {"type": "string"}, "phone": {"type": "string"},
                                     "persona_uid": {"type": "string"}, "request_id": {"type": "string"}}},
        handler=lambda a: phound_dry_run_call(a, env, suppression_file),
        # Scoped reversible simulation: writes only a dry-run call record
        # (working state). Can never place a live call (dry_run hard-coded).
        action_class=ActionClass.SAFE_WRITE,
    ))
    bus.register(MCPToolDefinition(
        name="browser_navigate_extract",
        description="Read-only browser page text extraction via Playwright. Allowed domains only.",
        input_schema={"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}},
        handler=lambda a: browser_navigate_extract(a, browser_fetcher),
        action_class=ActionClass.READ,
    ))
    return bus
