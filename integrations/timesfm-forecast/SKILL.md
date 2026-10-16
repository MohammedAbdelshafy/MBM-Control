# Skill: timesfm-forecast (free local forecasting)

Forecast time series **for free, locally, with no API key** — the
VibeFounder power #11 pattern (Google TimesFM, pretrained foundation model:
numbers in, forecast + uncertainty bands out, zero training, zero per-call
cost). Apache-2.0, 34k+ stars, verified 2026-10-16.

## When to use

- A DataClean AI client asks "what happens next?" — forecast their cleaned
  numeric series (signups, sales, traffic) as the upsell lane.
- MBM-Control needs a planning baseline: reply volume, pipeline cash,
  call-campaign spend before money is committed.
- Any "predict the next N weeks from these numbers" ask where a paid
  forecasting API would be margin-burn.

## Forecast (Python API)

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/timesfm-forecast")
from timesfm_forecast import forecast, summarize, backend_status

backend_status()   # {"fake": True, "timesfm": False|True, "timesfm_detail": ...}

r = forecast(
    [120,135,128,150,142,160,155,170,165,180,175,190],
    horizon=4,
    quantiles=[0.1, 0.5, 0.9],
    backend="timesfm",          # "fake" is the hermetic test double ONLY
    series_name="weekly_signups",
    frequency="weekly",
)
print(summarize(r))
print(r["point_forecast"])      # [.. 4 values ..]
print(r["quantile_bands"]["0.1"])  # lower band, etc.
```

## CSV input

```python
from timesfm_forecast import forecast
csv_text = open("sales.csv").read()
# or via MCP: forecast_csv tool with {"csv": ..., "column": "sales"}
```

## MCP server

```bash
python3 /home/hatch/workspace/night-shift/timesfm-forecast/mcp_server.py
# stdio JSON-RPC. Tools: forecast, forecast_csv, backend_status,
# validate_series, summarize, help
```

## Activation (one-time, ~1 GB)

```bash
pip install timesfm torch   # CPU torch is fine
# first forecast() downloads the checkpoint from HuggingFace (~800MB),
# then runs fully offline. No key, no account, no per-call cost.
```

## Rules

- Minimum 8 data points; horizon 1–512; quantiles sorted, in (0,1).
- **Every result carries the caveat:** the model sees numbers, not business
  context (launches, promos, regime changes). Forecasts are baselines, not
  guarantees — say so to the client, every time.
- `backend="timesfm"` without torch installed raises `BackendNotInstalled`
  with install steps. Never silently substitute the fake backend.
