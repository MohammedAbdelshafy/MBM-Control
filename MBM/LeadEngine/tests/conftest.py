"""Pytest isolation guard for MBM LeadEngine test suite.

Sets MBM_ARTIFACTS_ROOT to a throwaway directory BEFORE any production module
is imported, so no test can ever write into:

  MBM/Artifacts/**        (GTM, GLM, reports, suppression, quarantine)
  MBM/Clients/**
  mbm-dialer/app/public   (canonical dialer DB - guarded separately by tmp_path fixtures)

Production paths stay untouched; tests keep full strength (no skipped asserts).
"""

import os
import shutil
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

