# Wiring: Higgsfield Video → ClipOps Studio + FanForge

## ClipOps Studio (repo: `clipping-factory/`)

ClipOps's pipeline is candidate pool → auto-edit (ffmpeg) → **motion stage** →
content intelligence → distribution. Until now the motion stage had no real
AI-generation backend.

| ClipOps stage | Higgsfield tool | Job |
|---|---|---|
| motion stage | `higgsfield_submit` → `kling-video/v3.0-turbo/image-to-video` | animate a product/thumbnail still into a 5s hook clip |
| motion stage | `higgsfield_submit` → `bytedance/seedance-2.5/text-to-video` | generate b-roll from a script line when no footage exists |
| creative stage | `higgsfield_submit` → `higgsfield-ai/soul/v2/standard` | editorial thumbnails / cover art |
| packaging | `higgsfield_download` | pull finished media into the pipeline workspace |

Integration point (future build task): add a `HiggsfieldMotionAdapter` next to
the ffmpeg reframe step in `clipping-factory/` that calls `hf_client.submit`
+ `wait` and returns local MP4 paths. Not built tonight — this file is the
spec; the client + MCP server are the working foundation.

## FanForge (product offer lane)

Named capability: **"FanForge AI Video + Photoshoot"**.

- AI avatar photoshoot: `bytedance/seedance-2.5/reference-to-video` with
  client reference images → consistent-character short clips.
- Ad creatives: `marketing-studio/image` + Kling image→video → 5s product ads.
- Priced per deliverable (estimate via `higgsfield_estimate` × margin);
  Neteller rail per the repo AGENTS.md.

## MBM-Control

The skill + MCP server are drop-in for the GLM workforce: any swarm agent can
call `higgsfield_submit` (dry-run default) to prototype video deliverables
without writing integration code first.
