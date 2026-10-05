# TEST EVIDENCE — higgsfield-video (2026-10-05)

Command: `python3 test_smoke.py` in `~/workspace/night-shift/higgsfield-video/`
Environment: Python 3.12.3, no API key configured, network calls mocked.

## Result: 22/22 PASS (hermetic — no network, no key, no charge)

| Area | Tests | What they prove |
|---|---|---|
| Credentials | 4 | missing creds raise (never invented); key:secret pair form; single-token form; base-URL override |
| Input validation | 5 | Seedance t2v accepts valid payload; missing `prompt` rejected; unknown params rejected; unknown model rejected; Kling i2v requires `image_url` |
| Cost estimation | 3 | Seedance 2.5 × 5s = $0.369; Soul image = $0.0032 flat; Kling 3.0 × 10s = $1.12 |
| Dry-run submit | 1 | full validation + estimate with **zero** urllib calls |
| Live submit (mocked HTTP) | 2 | POST to `{base}/{model_id}` with `Key kid:ksecret` auth header; `request_id` returned; HTTP 401 surfaces as clean `HiggsfieldError` |
| Polling lifecycle | 5 | queued→in_progress→completed resolves + media URLs extracted; failed/nsfw raise; timeout raises; multi-image extraction |
| Download | 1 | 80 KB streamed to disk in chunks |
| MCP server (real stdio subprocess) | 1 | initialize handshake, tools/list (6 tools), tools/call: estimate, catalog (≥5 models), dry-run submit, unknown-model error path, unknown-method error |

Full output: all tests `ok`, `Ran 22 tests in 0.109s`, `OK`.

## What is NOT proven (honest gaps)

- No live paid generation has run (no API key exists on this machine).
- Request/response shapes are cross-checked across two independent community
  integrations + official FAQ; re-verify against docs.higgsfield.ai before the
  first paid call.
- Pricing snapshot dated 2026-10-05 from the official catalog; rates move.

## Activation blockers

1. **BLOCKED_ON_KEY**: founder must create a key at console.higgsfield.ai and
   set `HF_API_KEY_ID` + `HF_API_KEY_SECRET` (or `HIGGSFIELD_API_KEY`).
   Everything else is built and tested.
2. First paid call should re-check the catalog schema in docs.higgsfield.ai.
