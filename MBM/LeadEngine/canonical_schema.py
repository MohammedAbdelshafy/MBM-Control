#!/usr/bin/env python3
"""
canonical_schema.py — Single source of truth for the canonical deals memory schema.
====================================================================================
`canonical_deals_memory.json` is a JSON ARRAY (list) of canonical deal records.
Every diagnostic (audit / deep-dive / sellers audit) and the reconcile engine
MUST read it through this loader so audit → reconcile → verification gate all
agree on the same schema.

    canonical_deals_memory.json  →  [ {deal...}, {deal...}, ... ]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List


def load_canonical_memory(path: str | Path) -> List[dict]:
    """Load canonical deals memory and return a list of deal dicts.

    The canonical schema is a flat JSON list. For defensive compatibility the
    loader also accepts a JSON object wrapping a list under 'deals', 'leads',
    or 'records', but the REAL canonical file is a list and callers must not
    depend on the dict-wrapped form.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("deals", "leads", "records", "canonical_deals"):
            if isinstance(data.get(key), list):
                return data[key]
        raise ValueError(
            "canonical_deals_memory.json must be a JSON list of deals "
            f"(got dict with keys: {sorted(data.keys())})"
        )
    raise ValueError(
        "canonical_deals_memory.json must be a JSON list of deals "
        f"(got {type(data).__name__})"
    )


def assert_canonical_list(data: Any) -> None:
    """Hard guard: the canonical memory must be a list. Used by audit tooling
    so a schema regression fails loudly instead of silently misreading data."""
    if not isinstance(data, list):
        raise AssertionError(
            f"canonical_deals_memory.json schema regression: expected list, got {type(data).__name__}"
        )