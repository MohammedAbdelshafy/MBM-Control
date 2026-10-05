# Skill: higgsfield-video

Give an agent on-demand AI video and image generation through the Higgsfield API
(Seedance 2.5, Kling 3.0/2.6, MiniMax H3, Soul 2, Marketing Studio) for
**ClipOps Studio's motion stage** and **FanForge's AI-photoshoot / AI-drama lanes**.

## When to use

- A ClipOps clip needs a real AI-generated motion segment (text→video,
  image→video, product-photo animation).
- A FanForge client wants an AI avatar photoshoot, ad creative, or
  consistent-character episode art (reference→video on Seedance 2.5).
- NEVER use when: no `HF_API_KEY_ID`/`HF_API_KEY_SECRET` (or `HIGGSFIELD_API_KEY`)
  is configured — offer the dry-run path instead; never invent a key.

## Setup

```bash
export HF_API_KEY_ID='...' HF_API_KEY_SECRET='...'   # console.higgsfield.ai
# quick keyless check (validates + estimates, zero network):
python3 hf_client.py --prompt "test" --dry-run
```

## Agent workflow (mandatory order)

1. **Recommend the model** — call `higgsfield_catalog`, pick by task:
   text→video = `bytedance/seedance-2.5/text-to-video`;
   image→video (product photo) = `kling-video/v3.0-turbo/image-to-video`;
   character-consistent = `bytedance/seedance-2.5/reference-to-video`;
   editorial image = `higgsfield-ai/soul/v2/standard` (add "no lettering, no
   signage, no watermark" to the prompt);
   marketing image = `marketing-studio/image`.
2. **Estimate first** — `higgsfield_estimate(model_id, seconds)`. State the USD
   cost to the user before any live submit.
3. **Dry-run** — `higgsfield_submit(..., dry_run=true)` to validate the payload.
4. **Submit live only on explicit user go-ahead** — `dry_run=false` returns
   `request_id`; then `higgsfield_poll(request_id)`; then
   `higgsfield_download(url, filename)` into `outputs/`.
5. **Report** — model, seconds, estimated vs (if live) confirmed cost, file path.

## Budgets

No global spend cap is enforced by the API client. If the user sets a cap,
track estimates locally and refuse live submits that exceed it. Estimates can
differ from final charges; check the console analytics for ground truth.

## Failure modes

- `401/403` → key wrong or missing. Do not retry with variations.
- `failed`/`nsfw` → not charged; reword and re-estimate.
- Job stuck `queued` > 15 min → `wait()` raises; the request_id is preserved —
  resume with `higgsfield_poll(request_id)`.
