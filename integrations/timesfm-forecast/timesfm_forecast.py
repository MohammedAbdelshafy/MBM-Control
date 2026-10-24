#!/usr/bin/env python3
"""timesfm_forecast.py — free, local, no-key time-series forecasting.

Night-shift power #11 (VibeFounder 2026-10-15, row #78: Google TimesFM,
google-research/timesfm, Apache-2.0, verified 34,522 stars 2026-10-16).

What this is
-----------
A thin, honest adapter around Google's TimesFM pretrained forecasting
model. Feed it historical numbers (weekly sales, daily traffic, signups,
revenue); it returns a point forecast plus quantile bands for the next
`horizon` steps — with NO model training and NO API key, NO network, NO
cost after the one-time install.

What this is NOT
---------------
TimesFM sees numbers, not business context (the presenter's own caveat):
it does not know about launches, promotions, seasonality you forgot to
encode, or regime changes. Every forecast this module returns carries
that caveat in its metadata. Do not present a forecast as a guarantee.

Backends
--------
- "timesfm" (real): needs the pip package ``timesfm`` (v3.x, includes the
  TimesFM 2.5 torch backport) plus ``torch`` (CPU is fine) plus the
  pretrained checkpoint, downloaded once from HuggingFace on first run.
  Install: ``pip install timesfm torch`` then see README.
- "fake" (test double): deterministic synthetic forecast (linear trend +
  quantile bands scaled to residual variance). Used ONLY by the hermetic
  smoke tests and flagged ``backend="fake"`` in every result so it can
  never be mistaken for a real model output.

Stdlib-only except for the optional timesfm/torch pair. The MCP server
and the tests import only this module + stdlib.
"""

from __future__ import annotations

import math
import os
import time

ADAPTER_VERSION = "1.0.0"
POWER_ROW = 78
MIN_CONTEXT = 8
MAX_HORIZON = 512
DEFAULT_QUANTILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)

CAVEAT = ("TimesFM sees numbers, not business context: it does not know "
          "about launches, promotions, or regime changes. Treat every "
          "forecast as a baseline, not a guarantee.")

# Native quantile levels of the TimesFM-2.5 200M torch checkpoint
# (timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5_200M_Definition.quantiles).
NATIVE_QUANTILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
# Input patch length of TimesFM 2.5 — max_context must be a multiple of it.
TIMESFM_PATCH_LEN = 32
DEFAULT_CHECKPOINT_REPO = "google/timesfm-2.5-200m-pytorch"


class ForecastError(ValueError):
    """Raised for invalid input or unavailable backend."""


class BackendNotInstalled(ForecastError):
    """The real TimesFM backend is not installed on this machine."""


def validate_series(values, name="series"):
    """Validate a univariate series. Returns the cleaned list of floats."""
    if not isinstance(values, (list, tuple)):
        raise ForecastError(f"{name}: expected a list of numbers, got {type(values).__name__}")
    if len(values) < MIN_CONTEXT:
        raise ForecastError(
            f"{name}: need at least {MIN_CONTEXT} data points, got {len(values)}")
    cleaned = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ForecastError(f"{name}[{i}]: not a number: {v!r}")
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            raise ForecastError(f"{name}[{i}]: NaN/Inf not allowed")
        cleaned.append(f)
    return cleaned


def validate_horizon(horizon):
    if isinstance(horizon, bool) or not isinstance(horizon, int):
        raise ForecastError(f"horizon must be an int, got {horizon!r}")
    if not 1 <= horizon <= MAX_HORIZON:
        raise ForecastError(f"horizon must be 1..{MAX_HORIZON}, got {horizon}")
    return horizon


def validate_quantiles(quantiles):
    if quantiles is None:
        return list(DEFAULT_QUANTILES)
    if not isinstance(quantiles, (list, tuple)) or not quantiles:
        raise ForecastError("quantiles must be a non-empty list, e.g. [0.1, 0.5, 0.9]")
    qs = []
    for q in quantiles:
        if isinstance(q, bool) or not isinstance(q, (int, float)):
            raise ForecastError(f"quantile not a number: {q!r}")
        fq = float(q)
        if not 0.0 < fq < 1.0:
            raise ForecastError(f"quantile must be in (0, 1), got {q!r}")
        qs.append(fq)
    if sorted(qs) != qs:
        raise ForecastError("quantiles must be sorted ascending")
    if len(set(qs)) != len(qs):
        raise ForecastError("quantiles must be unique")
    return qs


def backend_status():
    """Report which backends are available on this machine."""
    status = {"fake": True, "timesfm": False, "timesfm_detail": None}
    try:
        import timesfm  # noqa: F401
    except ImportError:
        status["timesfm_detail"] = "pip package 'timesfm' not installed"
        return status
    try:
        import torch  # noqa: F401
    except ImportError:
        status["timesfm_detail"] = "'timesfm' installed but 'torch' missing (CPU torch is enough)"
        return status
    try:
        cls = timesfm.TimesFM_2p5_200M_torch
    except AttributeError:
        status["timesfm_detail"] = "'timesfm' installed but no torch forecaster class found"
        return status
    status["timesfm"] = True
    status["timesfm_detail"] = f"real backend available ({cls.__name__})"
    return status


def _fake_forecast(values, horizon, quantiles):
    """Deterministic test-double forecast. NEVER a real model output."""
    n = len(values)
    # Ordinary least squares trend on the series.
    sx = sum(range(n))
    sy = sum(values)
    sxx = sum(i * i for i in range(n))
    sxy = sum(i * v for i, v in enumerate(values))
    denom = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denom if denom else 0.0
    intercept = (sy - slope * sx) / n
    resid_var = sum((v - (intercept + slope * i)) ** 2 for i, v in enumerate(values)) / n
    resid_sd = math.sqrt(resid_var) if resid_var > 0 else 0.0
    point = [intercept + slope * (n + h) for h in range(horizon)]
    bands = {}
    for q in quantiles:
        # Normal-approx quantile offsets around the median, growing with horizon.
        z = _normal_ppf(q)
        bands[str(q)] = [p + z * resid_sd * math.sqrt(h + 1) for h, p in enumerate(point)]
    return point, bands, {"note": "fake backend: linear-trend test double, not a model"}


def _normal_ppf(p):
    """Inverse normal CDF (Acklam's approximation), stdlib only."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                 ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _resolve_checkpoint(repo_or_path):
    """Return a local checkpoint path for an HF repo id or an existing path.

    HF repos are downloaded once via huggingface_hub.snapshot_download into
    ~/.cache/timesfm/<repo__name> and reused on later runs (fully offline
    after the first download). Existing local paths are used as-is.
    """
    p = os.path.expanduser(repo_or_path)
    if os.path.exists(p):
        return p
    from huggingface_hub import snapshot_download
    cache = os.path.join(os.path.expanduser("~"), ".cache", "timesfm",
                         repo_or_path.replace("/", "__"))
    return snapshot_download(repo_id=repo_or_path, local_dir=cache)


def _timesfm_forecast(values, horizon, quantiles):
    """Real inference through the installed timesfm pip package (torch backend).

    Verified against timesfm 3.0.x: TimesFM_2p5_200M_torch takes a
    ForecastConfig, loads weights from a local path via load_checkpoint(),
    must be compile()d before forecast(), and forecast(horizon, [inputs])
    returns (point [n, H], quantiles [n, H, 9]) with native levels 0.1..0.9.
    """
    st = backend_status()
    if not st["timesfm"]:
        raise BackendNotInstalled(
            "Real TimesFM backend unavailable: " + st["timesfm_detail"] +
            ". Install with: pip install timesfm torch  (see README). "
            "Use backend='fake' only for hermetic tests.")
    import numpy as np  # timesfm requires numpy
    import timesfm
    from timesfm import ForecastConfig

    # max_context must be a multiple of the model's input patch length (32);
    # compile() rounds up, but rounding here keeps the intent explicit.
    raw_context = min(512, len(values))
    max_context = max(TIMESFM_PATCH_LEN,
                      (raw_context // TIMESFM_PATCH_LEN) * TIMESFM_PATCH_LEN)
    cfg = ForecastConfig(max_context=max_context, max_horizon=horizon,
                         normalize_inputs=True, infer_is_positive=False)
    model = timesfm.TimesFM_2p5_200M_torch(cfg)
    checkpoint = os.environ.get("TIMESFM_CHECKPOINT", DEFAULT_CHECKPOINT_REPO)
    local = _resolve_checkpoint(checkpoint)
    model.load_checkpoint(local)
    model.compile(cfg)
    inputs = np.asarray(values, dtype=np.float32)[-max_context:]
    t0 = time.time()
    point, quantiles_out = model.forecast(horizon, [inputs])
    elapsed = time.time() - t0
    point = [float(x) for x in np.asarray(point).reshape(-1)[:horizon]]
    qmap = np.asarray(quantiles_out)
    bands = {}
    if qmap.ndim == 3 and qmap.shape[2] == len(NATIVE_QUANTILES):
        for q in quantiles:
            idx = min(range(len(NATIVE_QUANTILES)),
                      key=lambda i: abs(NATIVE_QUANTILES[i] - q))
            bands[str(q)] = [float(x) for x in qmap[0, :horizon, idx].reshape(-1)]
    # If the checkpoint's quantile head differs, bands stay empty and the
    # caller reports point-only — never silently wrong bands.
    return point, bands, {
        "checkpoint": checkpoint,
        "inference_seconds": round(elapsed, 2),
        "model": "TimesFM-2.5-200M (torch)",
    }


def forecast(values, horizon=12, quantiles=None, backend="timesfm",
             series_name="series", frequency=None):
    """Forecast the next `horizon` steps of a univariate series.

    Returns a dict with point forecast, quantile bands, and metadata.
    Raises ForecastError on bad input, BackendNotInstalled when the real
    backend is requested but not installed.
    """
    vals = validate_series(values, name=series_name)
    h = validate_horizon(horizon)
    qs = validate_quantiles(quantiles)

    t0 = time.time()
    if backend == "fake":
        point, bands, extra = _fake_forecast(vals, h, qs)
        backend_used = "fake"
    elif backend == "timesfm":
        point, bands, extra = _timesfm_forecast(vals, h, qs)
        backend_used = "timesfm"
    else:
        raise ForecastError(f"unknown backend {backend!r}: use 'timesfm' or 'fake'")

    result = {
        "ok": True,
        "series_name": series_name,
        "frequency": frequency,
        "context_len": len(vals),
        "horizon": h,
        "quantiles": qs,
        "point_forecast": point,
        "quantile_bands": bands,
        "backend": backend_used,
        "adapter_version": ADAPTER_VERSION,
        "elapsed_seconds": round(time.time() - t0, 2),
        "caveat": CAVEAT,
    }
    result.update(extra or {})
    return result


def summarize(result):
    """One-paragraph human summary of a forecast result."""
    p = result["point_forecast"]
    lo = result["quantile_bands"].get("0.1") or result["quantile_bands"].get(str(min(result["quantiles"])))
    hi = result["quantile_bands"].get("0.9") or result["quantile_bands"].get(str(max(result["quantiles"])))
    lines = [
        f"Forecast for '{result['series_name']}' — next {result['horizon']} steps "
        f"(backend: {result['backend']}, context: {result['context_len']} points).",
        f"Point forecast: starts {p[0]:.2f}, ends {p[-1]:.2f} "
        f"({'up' if p[-1] >= p[0] else 'down'} {abs(p[-1]-p[0])/abs(p[0])*100:.1f}% across horizon)." if p[0] else
        f"Point forecast ends at {p[-1]:.2f}.",
    ]
    if lo and hi:
        lines.append(f"80% band at final step: [{lo[-1]:.2f}, {hi[-1]:.2f}].")
    lines.append("Caveat: " + result["caveat"])
    return "\n".join(lines)
