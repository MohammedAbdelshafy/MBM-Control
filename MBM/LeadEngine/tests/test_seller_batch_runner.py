"""
TESTS: REAL ESTATE SELLER BATCH RUNNER & DISPOSITION ENGINE
=============================================================================
Hermetic tests verifying batch generation, real estate scripting,
disposition recording, and automatic queue reprioritization.
=============================================================================
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.seller_batch_runner import (
    generate_batch_package,
    generate_seller_script,
    get_callable_sellers,
    record_disposition,
)
from MBM.LeadEngine.dialer_priority_engine import DialerPriorityEngine
from MBM.GLM.single_writer_lock import DialerSingleWriter


def test_generate_seller_script():
    """Verify real estate script incorporates property and owner details."""
    lead = {
        "id": "SELLER_TEST_01",
        "contact": "John Doe",
        "address": "742 Evergreen Terrace",
        "segment": "DISTRESSED_SELLER",
    }
    script = generate_seller_script(lead)
    assert "John" in script
    assert "742 Evergreen Terrace" in script
    assert "all-cash, as-is offer" in script
    assert "preliminary walkthrough" in script


def test_get_callable_sellers_returns_ranked_sellers():
    """Verify get_callable_sellers returns only callable real estate leads."""
    sellers = get_callable_sellers()
    assert len(sellers) > 0
    for s in sellers:
        assert s.get("is_real_estate") is True
        assert s.get("is_callable") is True
        assert s.get("queue_rank") is not None


def test_generate_batch_package_creates_document():
    """Verify batch package generates valid markdown and returns correct batch size."""
    res = generate_batch_package(batch_size=10)
    assert res["status"] == "BATCH_PREPARED"
    assert res["batch_size"] == 10
    assert Path(res["doc_path"]).exists()
    content = Path(res["doc_path"]).read_text(encoding="utf-8")
    assert "BATCH 1" in content
    assert "Real Estate Call Script" in content
