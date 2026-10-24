# TEST_EVIDENCE.md — timesfm-forecast

**Run:** 2026-10-16 ~03:00 EEST (night-shift) | **Repo verification:** GitHub API live check same night.

## 1. Upstream verification (no stubs: the power is real)

- `google-research/timesfm` via GitHub API 2026-10-16:
  - stars: **34,522** (the reel's "27,000" is understated)
  - license: **Apache-2.0** | archived: false | default branch: master
  - pushed_at: 2026-09-29T19:36:25Z | latest release: v3.0.0 (2026-08-28)
  - description: "TimesFM (Time Series Foundation Model) is a pretrained
    time-series foundation model developed by Google Research for
    time-series forecasting."
- PyPI `timesfm` 3.0.2 installs cleanly; stdlib-verified API surface:
  exports `ForecastConfig`, `timesfm_2p5`; `ForecastConfig` fields
  (max_context, max_horizon, normalize_inputs, infer_is_positive, …)
  match what `timesfm_forecast._timesfm_forecast` constructs;
  `timesfm.TimesFM_2p5_200M_torch` class exists (torch not installed here,
  so the import guard path is the exercised one).

## 2. Hermetic smoke tests — 18/18 PASS

`python3 test_smoke.py` — 2026-10-16 03:05 EEST, system python3, no network
dependency, no keys, no torch:

```
  PASS t_backend_status_shape
  PASS t_fake_constant_series
  PASS t_fake_deterministic
  PASS t_fake_shape
  PASS t_horizon_bounds
  PASS t_mcp_backend_status_and_help
  PASS t_mcp_csv_missing_column_is_error
  PASS t_mcp_forecast_csv
  PASS t_mcp_forecast_fake
  PASS t_mcp_init_and_tools
  PASS t_quantiles
  PASS t_real_backend_raises_helpful
  PASS t_summarize
  PASS t_unknown_backend
  PASS t_validate_nan
  PASS t_validate_non_numeric
  PASS t_validate_ok
  PASS t_validate_too_short
18 passed, 0 failed
```

What the tests actually prove:
- Validation rejects: <8 points, NaN/Inf, non-numeric, horizon 0/513,
  unsorted/dup/out-of-range quantiles, unknown backends.
- Fake-backend contract: point forecast length == horizon; quantile bands
  keyed by quantile string with matching lengths; OLS trend on a rising
  series points upward; bands ordered lo ≤ median ≤ hi at every step;
  constant series → constant forecast; deterministic across calls.
- MCP stdio: initialize → tools/list (6 tools) → tools/call round-trip;
  `notifications/initialized` gets NO response (true JSON-RPC notification
  semantics — the bolt-slides bug class, pre-empted);
  `forecast_csv` parses a header + named column; missing column returns
  `isError: true` with a ForecastError message.
- `backend="timesfm"` on a machine without torch raises
  `BackendNotInstalled` whose message contains the install command —
  never silently degrades to the fake backend.

## 3. Live-backend status — NOT verified on this VM (stated plainly)

- CPU-torch download from `download-r2.pytorch.org` hit read timeouts
  twice during this run (15s read timeout, retries exhausted). The
  checkpoint (~800MB from HuggingFace) was therefore not downloaded and
  **no real TimesFM inference ran on this VM**.
- The code path is written against the verified v3.0.2 API
  (`ForecastConfig` + `TimesFM_2p5_200M_torch` + `load_from_checkpoint`
  + `model.forecast(inputs, [horizon])`), and `backend_status()` reports
  exactly what is missing so activation is a single documented step.
- **Activation (one-time, ~1 GB, $0, no key):** on the forecast host,
  `pip install timesfm torch` (CPU fine) → first `forecast()` call
  downloads the checkpoint once → runs offline afterward. Override the
  checkpoint with `TIMESFM_CHECKPOINT=<hf-repo-id>`.

## 4. Integrity notes

- `fake` backend results always carry `"backend": "fake"` and a
  `"note": "fake backend: linear-trend test double, not a model"` —
  they cannot be mistaken for model output downstream.
- Every forecast result carries the business-context caveat in its
  `caveat` field and in `summarize()` output.
- No API keys, no network calls, no charges anywhere in this build.

## 5. Activation attempt 2026-10-24 — torch+timesfm installed, API fixed, checkpoint download pending approval

- **Install: SUCCESS.** This VM's system Python is PEP 668
  externally-managed (`pip install --user` is blocked too), so the live
  backend now lives in a venv: `~/workspace/tools/timesfm-venv`
  (`python3 -m venv`, then `pip install timesfm torch
  --extra-index-url https://download.pytorch.org/whl/cpu` — plain
  `--index-url` on the torch wheel index fails because `timesfm` is only
  on PyPI). Installed: **torch 2.14.1+cpu**, timesfm 3.0.x,
  huggingface_hub (ships with timesfm). `backend_status()` now reports
  `timesfm: true` — "real backend available (TimesFM_2p5_200M_torch)".
- **Real API mismatch found and fixed.** The 2026-10-16 code was written
  against an assumed API that does not exist in timesfm 3.0.x:
  `load_from_checkpoint(repo_id=...)` → real method is
  `load_checkpoint(path)` (local dir containing `model.safetensors`, or a
  file); `model.forecast(inputs, [horizon])` → real signature is
  `forecast(horizon, inputs)` with `inputs` a list of arrays; and
  `forecast()` raises `RuntimeError` unless `compile(cfg)` is called
  first. `timesfm_forecast._timesfm_forecast` was rewritten against the
  real signatures (verified by introspecting the installed package:
  `inspect.signature` on `load_checkpoint`, `compile`, `forecast`;
  native quantile levels `[0.1..0.9]` from
  `TimesFM_2p5_200M_Definition.quantiles`; `WEIGHTS_FILENAME =
  "model.safetensors"`). `max_context` is rounded to a multiple of the
  input patch length (32); checkpoint resolves via
  `huggingface_hub.snapshot_download` into `~/.cache/timesfm/` (once,
  then offline), or an existing local path via `TIMESFM_CHECKPOINT`.
- **Partially verified tonight (no checkpoint needed):**
  - 18/18 hermetic smoke tests still pass on system python3 (unchanged
    hermetic surface).
  - With `TIMESFM_CHECKPOINT=/tmp/empty-ckpt` (existing dir, no weights)
    under the venv python, `forecast(..., backend="timesfm")` now raises
    `FileNotFoundError: model.safetensors not found in directory
    /tmp/empty-ckpt` — i.e. the fixed `load_checkpoint` path validates
    correctly (previously this raised `AttributeError` on the
    nonexistent method).
  - New `test_live.py` added: end-to-end real-inference check
    (sentinel rising series, asserts real checkpoint id, point length,
    0.1/0.9 bands) — **not yet runnable**: see blocker.
- **Blocker: checkpoint download needs a one-time approval.** The first
  real `forecast()` downloads `google/timesfm-2.5-200m-pytorch` (~800MB)
  from huggingface.co. That read raised a schedule-scoped approval card
  ("Read huggingface.co on future runs of Vibefounder Night Shift",
  requested 2026-10-23 23:49 UTC), which cannot be approved on a detached
  run. The download was NOT attempted via any alternate route (no
  safeguard bypass). **What the founder must do:** approve that card once
  — it is schedule-scoped, so it covers all future night-shift runs.
  Next run after approval: `~/workspace/tools/timesfm-venv/bin/python
  test_live.py` downloads the checkpoint once and proves real inference;
  power #11 then moves to ACTIVATED.
