#!/usr/bin/env python3
"""Live activation test for power #11 (timesfm-forecast) — real TimesFM inference.

Run with the venv python: ~/workspace/tools/timesfm-venv/bin/python test_live.py
First run downloads the checkpoint (~800MB) from HuggingFace once, then runs offline.
"""
import json
import sys

sys.path.insert(0, "/home/hatch/workspace/night-shift/timesfm-forecast")

from timesfm_forecast import backend_status, forecast, summarize

print("backend_status:", json.dumps(backend_status()))

# Deterministic rising weekly-signups series (24 points).
values = [10 + 2 * i for i in range(24)]
res = forecast(values, horizon=6, backend="timesfm",
               series_name="weekly-signups", frequency="W")

assert res["ok"] is True
assert res["backend"] == "timesfm"
assert len(res["point_forecast"]) == 6
assert all(isinstance(x, float) for x in res["point_forecast"])
assert "0.1" in res["quantile_bands"] and "0.9" in res["quantile_bands"]
assert res["checkpoint"] == "google/timesfm-2.5-200m-pytorch"

print("backend:", res["backend"])
print("checkpoint:", res["checkpoint"])
print("inference_seconds:", res["inference_seconds"])
print("point_forecast:", [round(x, 2) for x in res["point_forecast"]])
print("80% band final step:",
      round(res["quantile_bands"]["0.1"][-1], 2),
      round(res["quantile_bands"]["0.9"][-1], 2))
print("---")
print(summarize(res))
print("---")
print("LIVE ACTIVATION TEST PASSED")
