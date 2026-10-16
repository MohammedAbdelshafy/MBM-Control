#!/usr/bin/env python3
"""Hermetic smoke tests for timesfm-forecast. No network, no keys, no torch.

All forecast tests run against the deterministic 'fake' backend test
double. The real TimesFM backend is exercised separately (see
TEST_EVIDENCE.md) and is NOT required for these tests to pass.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timesfm_forecast as tf

PASSED = []
FAILED = []


def check(name, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  PASS {name}")
    except Exception as e:
        FAILED.append((name, e))
        print(f"  FAIL {name}: {type(e).__name__}: {e}")


def expect_error(fn, fragment=""):
    try:
        fn()
    except tf.ForecastError as e:
        assert fragment in str(e), f"error {e!r} missing {fragment!r}"
        return
    raise AssertionError("expected ForecastError, got none")


# --- validation -----------------------------------------------------------
def t_validate_ok():
    out = tf.validate_series([1.0, 2, 3, 4, 5, 6, 7, 8, 9])
    assert out == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]


def t_validate_too_short():
    expect_error(lambda: tf.validate_series([1, 2, 3]), "at least 8")


def t_validate_nan():
    expect_error(lambda: tf.validate_series([1, 2, 3, 4, 5, 6, 7, float("nan")]), "NaN/Inf")


def t_validate_non_numeric():
    expect_error(lambda: tf.validate_series([1, 2, 3, 4, 5, 6, 7, "x"]), "not a number")


def t_horizon_bounds():
    expect_error(lambda: tf.validate_horizon(0), "1..512")
    expect_error(lambda: tf.validate_horizon(513), "1..512")
    assert tf.validate_horizon(12) == 12


def t_quantiles():
    expect_error(lambda: tf.validate_quantiles([0.9, 0.1]), "sorted")
    expect_error(lambda: tf.validate_quantiles([0.5, 0.5]), "unique")
    expect_error(lambda: tf.validate_quantiles([1.5]), "in (0, 1)")
    assert tf.validate_quantiles(None) == list(tf.DEFAULT_QUANTILES)
    assert tf.validate_quantiles([0.1, 0.5, 0.9]) == [0.1, 0.5, 0.9]


def t_unknown_backend():
    expect_error(lambda: tf.forecast(list(range(10)), backend="nope"), "unknown backend")


# --- fake-backend forecast contract ----------------------------------------
SERIES = [100 + 2 * i + (i % 3) for i in range(24)]  # rising trend + noise


def t_fake_shape():
    r = tf.forecast(SERIES, horizon=6, quantiles=[0.1, 0.5, 0.9], backend="fake",
                    series_name="weekly_sales", frequency="weekly")
    assert r["ok"] and r["backend"] == "fake"
    assert len(r["point_forecast"]) == 6
    assert set(r["quantile_bands"]) == {"0.1", "0.5", "0.9"}
    assert all(len(v) == 6 for v in r["quantile_bands"].values())
    assert r["context_len"] == 24 and r["horizon"] == 6
    assert "numbers, not business context" in r["caveat"]
    # trend continues upward (OLS on rising series)
    assert r["point_forecast"][-1] > r["point_forecast"][0]
    # bands ordered: lo < median < hi everywhere
    lo, med, hi = (r["quantile_bands"][k] for k in ("0.1", "0.5", "0.9"))
    assert all(l <= m <= h for l, m, h in zip(lo, med, hi))


def t_fake_deterministic():
    a = tf.forecast(SERIES, horizon=4, backend="fake")["point_forecast"]
    b = tf.forecast(SERIES, horizon=4, backend="fake")["point_forecast"]
    assert a == b


def t_fake_constant_series():
    r = tf.forecast([5.0] * 12, horizon=3, backend="fake")
    assert all(abs(p - 5.0) < 1e-9 for p in r["point_forecast"])


def t_summarize():
    r = tf.forecast(SERIES, horizon=4, quantiles=[0.1, 0.9], backend="fake",
                    series_name="signups")
    s = tf.summarize(r)
    assert "signups" in s and "next 4 steps" in s and "Caveat" in s


def t_backend_status_shape():
    st = tf.backend_status()
    assert st["fake"] is True
    assert isinstance(st["timesfm"], bool)
    assert isinstance(st.get("timesfm_detail"), str)


def t_real_backend_raises_helpful():
    st = tf.backend_status()
    if st["timesfm"]:
        print("    (real backend installed — skipping not-installed check)")
        return
    try:
        tf.forecast(SERIES, horizon=2, backend="timesfm")
    except tf.BackendNotInstalled as e:
        assert "pip install timesfm torch" in str(e)
        return
    raise AssertionError("expected BackendNotInstalled")


# --- MCP stdio round-trip ---------------------------------------------------
def mcp_session(requests):
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    out, _ = proc.communicate("\n".join(json.dumps(r) for r in requests) + "\n",
                              timeout=60)
    return [json.loads(ln) for ln in out.splitlines() if ln.strip()]


def t_mcp_init_and_tools():
    resps = mcp_session([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    assert len(resps) == 2, f"notification must not get a response, got {len(resps)}"
    names = [t["name"] for t in resps[1]["result"]["tools"]]
    for want in ("forecast", "forecast_csv", "backend_status", "validate_series", "summarize", "help"):
        assert want in names, f"missing tool {want}"
    assert resps[0]["result"]["serverInfo"]["name"] == "timesfm-forecast"


def t_mcp_forecast_fake():
    (resp,) = mcp_session([
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "forecast",
                    "arguments": {"values": SERIES, "horizon": 3,
                                  "quantiles": [0.1, 0.5, 0.9],
                                  "backend": "fake", "series_name": "traffic"}}},
    ])
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["ok"] and body["backend"] == "fake"
    assert len(body["point_forecast"]) == 3
    assert resp["result"]["isError"] is False


def t_mcp_forecast_csv():
    csv = "week,sales\n1,10\n2,12\n3,11\n4,13\n5,14\n6,15\n7,16\n8,17\n9,18\n"
    (resp,) = mcp_session([
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "forecast_csv",
                    "arguments": {"csv": csv, "column": "sales", "horizon": 2,
                                  "backend": "fake"}}},
    ])
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["ok"] and body["series_name"] == "sales"
    assert len(body["point_forecast"]) == 2


def t_mcp_csv_missing_column_is_error():
    (resp,) = mcp_session([
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "forecast_csv",
                    "arguments": {"csv": "a,b\n1,2\n", "column": "nope",
                                  "backend": "fake"}}},
    ])
    assert resp["result"]["isError"] is True
    assert "ForecastError" in resp["result"]["content"][0]["text"]


def t_mcp_backend_status_and_help():
    r1, r2 = mcp_session([
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
         "params": {"name": "backend_status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
         "params": {"name": "help", "arguments": {}}},
    ])
    st = json.loads(r1["result"]["content"][0]["text"])
    assert st["fake"] is True
    h = json.loads(r2["result"]["content"][0]["text"])
    assert "pip install timesfm torch" in h["help"]


def main():
    print("timesfm-forecast smoke tests (hermetic: fake backend only)")
    for name, fn in sorted([(k, v) for k, v in globals().items() if k.startswith("t_")]):
        check(name, fn)
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
