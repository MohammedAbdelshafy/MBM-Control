# Higgsfield Video — unified AI video/image generation for ClipOps Studio + FanForge

**VibeFounder power #4** (2026-10-05): "Generate AI video via a unified image+video API"
— the reel the founder watched (Seedance 2.5 + Kling behind one key).

This package wires the verified-live **Higgsfield API** into the founder's stack as a
named, documented capability: **ClipOps Studio gains a real video-generation backend
for its motion stage**, and **FanForge gains an "AI video + photoshoot" offer lane**.
See `WIRING.md` for the product mapping.

## Status: BUILT + TESTED — activation BLOCKED_ON_KEY

The API is live and pay-as-you-go (verified 2026-10-05 at higgsfield.ai).
Everything here is real and runnable, but **live generation needs a paid API key
the founder does not have yet** — dry-run mode needs no key at all.

## What this is

- `hf_client.py` — stdlib-only client: submit → poll → download, input
  validation against the model catalog, pre-flight USD estimates. No deps.
- `mcp_server.py` — stdlib-only MCP stdio server (6 tools) for Claude Code /
  Cursor agents. No `mcp` package needed.
- `model_catalog.json` — 7 models (Seedance 2.5, Kling 3.0/2.6, MiniMax H3,
  Soul 2, Marketing Studio) with snapshot pricing from the official catalog.
- `test_smoke.py` — 22 hermetic tests: no network, no key, no charge.
- `SKILL.md` — reusable agent skill.
- `WIRING.md` — how this plugs into ClipOps Studio's motion stage + FanForge.

## Activate (founder)

1. Sign up at console.higgsfield.ai, top up a USD balance (launch offer: $15 on
   balance + up to 50% model discounts), create an API key.
2. Export credentials — **environment only, never commit**:
   ```bash
   export HF_API_KEY_ID='...' HF_API_KEY_SECRET='...'
   # or a single token: export HIGGSFIELD_API_KEY='...'
   ```
3. Smoke-test a live submit (pay-as-you-go; a 5s Seedance 2.5 clip ≈ $0.37):
   ```bash
   python3 hf_client.py --prompt "cinematic tracking shot, coastal road at sunset" \
     --seconds 5 --live --wait
   ```
4. Re-verify `model_catalog.json` pricing against the console before quoting
   clients — snapshot date is 2026-10-05.

## Agent use (MCP)

```json
{"mcpServers": {"higgsfield-video": {
  "command": "python3",
  "args": ["<abs path>/mcp_server.py"],
  "env": {"HF_API_KEY_ID": "...", "HF_API_KEY_SECRET": "..."}}}}
```

Dry-run everything first: `higgsfield_submit(..., dry_run=true)` validates the
payload and returns a cost estimate with zero network calls.

## Pricing snapshot (2026-10-05, official catalog)

| Model | Rate |
|---|---|
| Seedance 2.5 (video) | $0.0738/sec |
| Kling 3.0 (video) | $0.112/sec |
| Kling 2.6 (video) | $0.07/sec |
| MiniMax H3 (video) | $0.13/sec |
| Soul 2 (image) | $0.0032/image |
| Marketing Studio (image) | $0.0059/image |

Failed/NSFW generations are not charged (refunded automatically). Always call
`higgsfield_estimate` before a live submit.

## Test evidence

`python3 test_smoke.py` — 22/22 pass, hermetic. Full log in `TEST_EVIDENCE.md`.

## Branch

Built on `night-shift/vibefounder-powers` in MohammedAbdelshafy/MBM-Control
(never master). Mirror of this folder: `integrations/higgsfield-video/`.
