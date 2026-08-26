"""Real Estate AI Media vertical (owner directive 2026-08-26, D-021).

Design law:
- Pure logic lives in plain-python modules (hermetically testable, no Frappe
  runtime required). Frappe DocType JSONs in contec/doctype/ persist state.
- Providers are adapters behind one interface. A provider that is not
  configured reports available()=False and is skipped - never simulated.
- No fabricated business facts: missing listing data = UNKNOWN / NEEDS_REVIEW.
- AI/media outputs never post financial transactions (D-019).
"""
from .state_machine import DIALER_STATES, CRM_STAGES, transition  # noqa: F401
from .scoring import real_estate_media_score  # noqa: F401
from .lead_dedup import dedup_key  # noqa: F401
