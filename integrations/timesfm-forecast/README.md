# timesfm-forecast — free local forecasting (VibeFounder power #11)

**Source:** @thevibefounder reel 2026-10-15 (backlog row #78): Google **TimesFM** —
a pretrained time-series foundation model. Feed it historical numbers (weekly
sales, daily traffic, signups, revenue); it forecasts the future **without
training a model, without an API key, without network, and without per-call
cost** after a one-time install.

**Verified 2026-10-16:** `google-research/timesfm` — 34,522 stars, Apache-2.0,
pushed 2026-09-29, latest release v3.0.0. (The reel says "27,000 stars" —
understated; the repo is bigger now.)

## What it is

A thin adapter (`timesfm_forecast.py`) + stdlib-only MCP stdio server
(`mcp_server.py`) around TimesFM 2.5 (the torch backport shipped in the
`timesfm` v3.x pip package). Input: a list of numbers (or CSV). Output:
point forecast + quantile bands + metadata for the next N steps.

**The honest limit (stated in every result):** TimesFM sees numbers, not
business context — it does not know about launches, promotions, or regime
changes. Every forecast carries that caveat. Baselines, not guarantees.

## Install

Hermetic parts (validation, MCP server, tests) need **only stdlib Python 3**.

For real inference (one-time, ~1 GB total):

```bash
pip install timesfm torch          # CPU torch is fine
# first forecast() call downloads the checkpoint from HuggingFace once (~800MB),
# then runs fully offline. Override with TIMESFM_CHECKPOINT=<hf-repo-id>.
```

No API key. No account. No cost per forecast.

## Use

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/timesfm-forecast")
from timesfm_forecast import forecast, summarize, backend_status

print(backend_status())                      # {"fake": True, "timesfm": False, ...}
r = forecast([120,135,128,150,142,160,155,170,165,180,175,190],
             horizon=4, quantiles=[0.1,0.5,0.9],
             backend="timesfm",              # or "fake" (test double only)
             series_name="weekly_signups", frequency="weekly")
print(summarize(r))
```

MCP server: `python3 mcp_server.py` (JSON-RPC 2.0 over stdio). Tools:
`forecast`, `forecast_csv`, `backend_status`, `validate_series`, `summarize`, `help`.

## Backends

| backend | what it is | when to use |
|---|---|---|
| `timesfm` | Real TimesFM-2.5-200M inference (torch, CPU ok) | production forecasts |
| `fake` | Deterministic linear-trend test double, flagged in every result | smoke tests only |

`backend="timesfm"` without torch/timesfm installed raises
`BackendNotInstalled` with install instructions — never silently degrades.

## Tests

```bash
python3 test_smoke.py   # 18/18 hermetic, no network/key/torch
```

## Wiring

See `WIRING.md` for the product mapping (DataClean AI "Forecasts" lane,
MBM-Control internal ops). See `TEST_EVIDENCE.md` for the test record.
