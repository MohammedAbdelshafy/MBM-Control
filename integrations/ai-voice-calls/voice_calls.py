#!/usr/bin/env python3
"""AI voice calls — outbound (and inbound-ready) AI voice agent calling.

Stdlib-only client + campaign layer for a voice-AI provider with a
documented REST API (default: Vapi, https://api.vapi.ai).

This is the VibeFounder night-shift build for power #10
("Run human-like AI voice calls for support/sales" — the Giga reel):
the founder's Wholesaler Lead Engine + AI Front Desk gain an AI-voice
calling lane, with compliance guardrails baked in.

Provider status:
- Giga (the reel's vendor) is an enterprise voice-AI platform with no
  public self-serve API verified from here — integration target for it
  is a per-client enterprise deal, not a repo adapter.
- Vapi exposes a documented public REST API (api.vapi.ai), so the
  concrete adapter below targets Vapi's endpoints:
    POST /assistant          create an assistant
    GET  /assistant/{id}     fetch an assistant
    POST /call               start an outbound phone call
    GET  /call               list calls
    GET  /call/{id}          fetch one call
    PATCH /call/{id}         update a call (e.g. end it early)
  Authentication: `Authorization: Bearer <VAPI_API_KEY>`.

Config slots (env only, never committed):
  VAPI_API_KEY            paid key from dashboard.vapi.ai
  VAPI_ASSISTANT_ID       optional default assistant
  VAPI_PHONE_NUMBER_ID    optional default Vapi phone number
  VAPI_BASE_URL           override for tests / self-host

Status: BUILT + TESTED — activation BLOCKED_ON_KEY (needs a paid
Vapi account; the founder currently has no card on file — Neteller only).
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

DEFAULT_BASE_URL = "https://api.vapi.ai"
TERMINAL_STATUSES = {"ended", "cancelled", "failed"}

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

# Phrases that count as an AI-identity disclosure in an assistant's
# first message. Several US states require callers to disclose that the
# caller is AI; the campaign runner enforces this by default.
DISCLOSURE_PHRASES = (
    "ai assistant",
    "ai voice assistant",
    "artificial intelligence",
    "automated assistant",
    "automated voice assistant",
    "virtual assistant",
    "i'm an ai",
    "i am an ai",
    "this is an ai",
    "ai agent",
    "digital assistant",
)

# --- cost model -------------------------------------------------------------
# Vapi's documented platform fee is $0.05/min; third-party 2026 estimates
# put realistic all-in cost (model + voice + STT + telephony) at
# $0.07–$0.25/min. All rates below are parameters with those defaults;
# re-check against the vendor's current pricing page before quoting.
DEFAULT_RATES = {
    "platform_per_min": 0.05,
    "all_in_low_per_min": 0.07,
    "all_in_high_per_min": 0.25,
    "voicemail_overhead_pct": 0.20,  # unanswered/voicemail minutes overhead
}


class VoiceCallsError(Exception):
    """Base error for this module."""


class ConfigError(VoiceCallsError):
    """Missing or invalid configuration (e.g. no API key)."""


class ValidationError(VoiceCallsError):
    """Invalid input — bad phone number, bad CSV, compliance failure."""


class ApiError(VoiceCallsError):
    """The provider API returned an error."""

    def __init__(self, status: int, message: str):
        super().__init__(f"API {status}: {message}")
        self.status = status


# --- config -----------------------------------------------------------------

@dataclass
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    assistant_id: str | None = None
    phone_number_id: str | None = None
    timeout_s: int = 30

    @classmethod
    def from_env(cls, require_key: bool = True) -> "Config":
        key = os.environ.get("VAPI_API_KEY", "").strip()
        if require_key and not key:
            raise ConfigError(
                "VAPI_API_KEY is not set. Create one at dashboard.vapi.ai "
                "(paid account), then: export VAPI_API_KEY='...'. "
                "Never commit the key."
            )
        return cls(
            api_key=key,
            base_url=os.environ.get("VAPI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            assistant_id=os.environ.get("VAPI_ASSISTANT_ID") or None,
            phone_number_id=os.environ.get("VAPI_PHONE_NUMBER_ID") or None,
        )

    def key_set(self) -> bool:
        return bool(self.api_key)


# --- validation / compliance -------------------------------------------------

def validate_e164(number: str) -> str:
    """Validate an E.164 phone number, raising ValidationError if bad."""
    n = (number or "").strip().replace(" ", "").replace("-", "")
    if not E164_RE.match(n):
        raise ValidationError(
            f"not a valid E.164 phone number: {number!r} "
            "(expected e.g. +14155551234)"
        )
    return n


def ensure_ai_disclosure(first_message: str, enforce: bool = True) -> None:
    """Require the assistant's opening line to disclose it is AI.

    Many US states require AI-identity disclosure on outbound calls.
    Enforced by default; pass enforce=False only where a human operator
    has confirmed disclosure happens another way (logged, auditable).
    """
    text = (first_message or "").lower()
    if enforce and not any(p in text for p in DISCLOSURE_PHRASES):
        raise ValidationError(
            "first message does not disclose the caller is AI "
            f"(must contain one of: {', '.join(sorted(DISCLOSURE_PHRASES))})"
        )


@dataclass
class DncList:
    """Do-Not-Call suppression list (numbers that must never be dialed)."""

    numbers: set = field(default_factory=set)

    @classmethod
    def from_csv(cls, path: str | Path) -> "DncList":
        p = Path(path)
        if not p.exists():
            return cls()
        nums = set()
        with p.open(newline="") as f:
            for row in csv.reader(f):
                if row:
                    try:
                        nums.add(validate_e164(row[0]))
                    except ValidationError:
                        continue  # ignore malformed entries in the DNC file
        return cls(nums)

    def add(self, number: str) -> None:
        self.numbers.add(validate_e164(number))

    def is_suppressed(self, number: str) -> bool:
        try:
            return validate_e164(number) in self.numbers
        except ValidationError:
            return True  # unparseable numbers are never dialed


@dataclass
class Lead:
    number: str
    name: str = ""
    consent: bool = True
    metadata: dict = field(default_factory=dict)


def load_leads_csv(path: str | Path, require_consent: bool = True) -> tuple[list[Lead], list[str]]:
    """Load campaign leads from CSV. Returns (leads, warnings).

    Columns: number (required), name, consent (true/false/1/0),
    plus any extra columns carried into metadata.
    """
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"leads CSV not found: {path}")
    leads, warnings, seen = [], [], set()
    with p.open(newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            raw = (row.get("number") or "").strip()
            if not raw:
                warnings.append(f"row {i}: missing number, skipped")
                continue
            try:
                number = validate_e164(raw)
            except ValidationError:
                warnings.append(f"row {i}: invalid number {raw!r}, skipped")
                continue
            if number in seen:
                warnings.append(f"row {i}: duplicate {number}, skipped")
                continue
            seen.add(number)
            consent_raw = str(row.get("consent", "true")).strip().lower()
            consent = consent_raw in ("true", "1", "yes", "y")
            if require_consent and not consent:
                warnings.append(f"row {i}: {number} lacks consent, skipped")
                continue
            meta = {k: v for k, v in row.items()
                    if k not in ("number", "name", "consent")}
            leads.append(Lead(number=number,
                              name=(row.get("name") or "").strip(),
                              consent=consent,
                              metadata=meta))
    return leads, warnings


# --- provider client ---------------------------------------------------------

class VapiClient:
    """Stdlib HTTP client for the Vapi REST API."""

    def __init__(self, config: Config):
        if not config.api_key:
            raise ConfigError("VAPI_API_KEY is not set (see Config.from_env)")
        self.cfg = config

    def _request(self, method: str, path: str, body: dict | None = None,
                 params: dict | None = None) -> dict:
        url = self.cfg.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.cfg.api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as resp:
                raw = resp.read().decode() or "{}"
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode()[:500]
            except Exception:
                detail = ""
            raise ApiError(e.code, detail or e.reason) from e
        except urllib.error.URLError as e:
            raise ApiError(0, f"network error: {e.reason}") from e

    # -- assistants ---------------------------------------------------------

    def create_assistant(self, assistant: dict) -> dict:
        """Create an assistant (POST /assistant). Pass-through config dict."""
        if not isinstance(assistant, dict) or not assistant.get("model"):
            raise ValidationError(
                "assistant config must be a dict with at least a 'model' key"
            )
        return self._request("POST", "/assistant", assistant)

    def get_assistant(self, assistant_id: str) -> dict:
        return self._request("GET", f"/assistant/{assistant_id}")

    def build_default_assistant(self, *, system_prompt: str,
                                first_message: str,
                                voice_provider: str = "11labs",
                                model_provider: str = "openai",
                                model_name: str = "gpt-4o-mini",
                                enforce_disclosure: bool = True) -> dict:
        """Build a standard outbound assistant config (not sent until
        create_assistant is called)."""
        ensure_ai_disclosure(first_message, enforce=enforce_disclosure)
        return {
            "name": "outbound-sales-qualification",
            "firstMessage": first_message,
            "model": {
                "provider": model_provider,
                "model": model_name,
                "systemPrompt": system_prompt,
            },
            "voice": {"provider": voice_provider},
        }

    # -- calls ---------------------------------------------------------------

    def start_call(self, customer_number: str, *,
                   assistant_id: str | None = None,
                   phone_number_id: str | None = None,
                   assistant_overrides: dict | None = None,
                   metadata: dict | None = None,
                   enforce_disclosure: bool = True) -> dict:
        """Start an outbound phone call (POST /call)."""
        number = validate_e164(customer_number)
        aid = assistant_id or self.cfg.assistant_id
        if not aid:
            raise ValidationError(
                "no assistant_id given and VAPI_ASSISTANT_ID is not set")
        pid = phone_number_id or self.cfg.phone_number_id
        if not pid:
            raise ValidationError(
                "no phone_number_id given and VAPI_PHONE_NUMBER_ID is not set")
        if enforce_disclosure and assistant_overrides:
            fm = (assistant_overrides.get("firstMessage")
                  or assistant_overrides.get("variableValues", {}).get("firstMessage")
                  or "")
            if fm:
                ensure_ai_disclosure(fm, enforce=True)
        payload: dict = {
            "assistantId": aid,
            "phoneNumberId": pid,
            "customer": {"number": number},
        }
        if assistant_overrides:
            payload["assistantOverrides"] = assistant_overrides
        if metadata:
            payload["metadata"] = metadata
        return self._request("POST", "/call", payload)

    def get_call(self, call_id: str) -> dict:
        return self._request("GET", f"/call/{call_id}")

    def list_calls(self, limit: int = 20, created_after: str | None = None) -> list:
        params: dict = {"limit": max(1, min(limit, 100))}
        if created_after:
            params["createdAtGt"] = created_after
        data = self._request("GET", "/call", params=params)
        return data if isinstance(data, list) else data.get("calls", [])

    def end_call(self, call_id: str) -> dict:
        """End a call early (PATCH /call/{id})."""
        return self._request("PATCH", f"/call/{call_id}", {"status": "ended"})

    def wait_call(self, call_id: str, timeout_s: int = 600,
                  poll_s: int = 5) -> dict:
        """Poll get_call until the call reaches a terminal status."""
        deadline = time.time() + timeout_s
        last = {}
        while time.time() < deadline:
            last = self.get_call(call_id)
            if last.get("status") in TERMINAL_STATUSES:
                return last
            time.sleep(poll_s)
        raise VoiceCallsError(
            f"call {call_id} did not reach a terminal status within "
            f"{timeout_s}s (last status: {last.get('status')})"
        )


# --- cost estimation ----------------------------------------------------------

def estimate_cost(num_calls: int, avg_minutes: float = 2.0,
                  rates: dict | None = None) -> dict:
    """Pre-flight USD estimate. No network, never charged.

    Rates are parameters (defaults = documented Vapi platform fee $0.05/min
    and 2026 third-party all-in estimates $0.07–$0.25/min)."""
    r = {**DEFAULT_RATES, **(rates or {})}
    minutes = num_calls * avg_minutes * (1 + r["voicemail_overhead_pct"])
    return {
        "num_calls": num_calls,
        "avg_minutes": avg_minutes,
        "billable_minutes": round(minutes, 1),
        "platform_fee_usd": round(minutes * r["platform_per_min"], 2),
        "all_in_low_usd": round(minutes * r["all_in_low_per_min"], 2),
        "all_in_high_usd": round(minutes * r["all_in_high_per_min"], 2),
        "note": "estimates only — re-check the vendor pricing page before quoting",
    }


# --- campaign runner ------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CampaignRunner:
    """Dispatch outbound AI calls over a lead list, with pacing + logging."""

    client: VapiClient | None = None
    dnc: DncList = field(default_factory=DncList)
    dry_run: bool = True
    log_path: Path | None = None

    def run(self, leads: list[Lead], *, assistant_id: str | None = None,
            phone_number_id: str | None = None,
            assistant_overrides: dict | None = None,
            interval_s: float = 10.0,
            enforce_disclosure: bool = True) -> list[dict]:
        """Run the campaign. dry_run=True simulates everything (no HTTP,
        no charge, no real calls). Returns per-lead result dicts and
        appends JSONL records to log_path."""
        results = []
        for lead in leads:
            rec = {"number": lead.number, "name": lead.name,
                   "started_at": _now_iso(), "mode": "dry-run" if self.dry_run else "live"}
            if self.dnc.is_suppressed(lead.number):
                rec.update(status="suppressed", reason="DNC list")
            elif self.dry_run:
                rec.update(status="dry-run-ok",
                           note="no call placed; remove dry_run to go live")
            else:
                try:
                    call = self.client.start_call(
                        lead.number, assistant_id=assistant_id,
                        phone_number_id=phone_number_id,
                        assistant_overrides=assistant_overrides,
                        metadata={"lead_name": lead.name, **lead.metadata},
                        enforce_disclosure=enforce_disclosure)
                    rec.update(status="started", call_id=call.get("id"))
                except VoiceCallsError as e:
                    rec.update(status="error", reason=str(e))
            rec["finished_at"] = _now_iso()
            results.append(rec)
            if self.log_path:
                with self.log_path.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
            if interval_s > 0 and lead is not leads[-1]:
                time.sleep(interval_s)
        return results


# --- CLI --------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="AI voice calls (Vapi adapter)")
    ap.add_argument("--estimate", type=int, metavar="N",
                    help="estimate cost for N outbound calls")
    ap.add_argument("--avg-minutes", type=float, default=2.0)
    ap.add_argument("--config-check", action="store_true",
                    help="report which config slots are set (no secrets shown)")
    args = ap.parse_args()

    if args.estimate is not None:
        print(json.dumps(estimate_cost(args.estimate, args.avg_minutes), indent=2))
    elif args.config_check:
        cfg = Config.from_env(require_key=False)
        print(json.dumps({
            "VAPI_API_KEY": "set" if cfg.key_set() else "MISSING",
            "VAPI_ASSISTANT_ID": "set" if cfg.assistant_id else "not set",
            "VAPI_PHONE_NUMBER_ID": "set" if cfg.phone_number_id else "not set",
            "VAPI_BASE_URL": cfg.base_url,
        }, indent=2))
    else:
        ap.print_help()
