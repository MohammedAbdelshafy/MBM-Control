"""Pytest isolation guard + path bootstrap for the MBM LeadEngine test suite.

1. Isolation guard: sets MBM_ARTIFACTS_ROOT to a throwaway directory BEFORE
   any production module is imported, so no test can ever write into:

     MBM/Artifacts/**        (GTM, GLM, reports, suppression, quarantine)
     MBM/Clients/**
     mbm-dialer/app/public   (canonical dialer DB - guarded separately by tmp_path fixtures)

   Production paths stay untouched; tests keep full strength (no skipped asserts).

2. Path bootstrap: exposes both the repo root (for `MBM.*` package imports)
   and the LeadEngine dir (for `pain_to_offer` / `property_intel` style
   imports) on sys.path.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TEST_ARTIFACTS_ROOT = tempfile.mkdtemp(prefix="mbm_test_artifacts_")
os.environ["MBM_ARTIFACTS_ROOT"] = _TEST_ARTIFACTS_ROOT

# Seed read-only INPUT fixtures (copied, never mutated) so tests that consume
# real supply (e.g. AIAssistantBuyerHunter NPI discovery) see production data
# while every WRITE lands inside the isolated root.
_PROD_ARTIFACTS = Path(__file__).resolve().parents[2] / "Artifacts"
for _name in ("npi_verified_callsheet.json",):
    _src = _PROD_ARTIFACTS / _name
    if _src.exists():
        shutil.copy2(_src, Path(_TEST_ARTIFACTS_ROOT) / _name)

_REPO_ROOT = str(Path(__file__).resolve().parents[3])
_LEADENGINE = str(Path(__file__).resolve().parents[1])
for _p in (_REPO_ROOT, _LEADENGINE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
