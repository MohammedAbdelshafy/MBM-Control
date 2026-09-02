import sys
from pathlib import Path

LEADENGINE = Path(__file__).resolve().parents[1]
if str(LEADENGINE) not in sys.path:
    sys.path.insert(0, str(LEADENGINE))

import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "live: live provider contract test (requires env vars, excluded from CI)")