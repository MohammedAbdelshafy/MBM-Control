# MBM Instagram Intelligence System — Mission

**Owner:** Jarvis (MBM Operations Layer)
**Status:** ACTIVE — Phase 1 (scaffolding)

## Objective
Turn the operator's own authenticated Instagram account into a searchable, structured
intelligence database built from Saved / Liked / Collection / Following / Explore Reels.
Operate ONLY within content the logged-in account can legitimately view. Never bypass auth
or access private content. Respect Instagram ToS.

## Phases
1. Scaffolding — folders, config, schema, SQLite DBs, Markdown template.  ✅ in progress
2. Collector — read Reels via authenticated browser session (chrome-devtools MCP / Playwright).
3. Analysis — OCR (PaddleOCR), speech (whisper/ollama), vision (local VLMs: Qwen2.5-VL etc).
4. Scoring & Classification — hook type, psychology, sales analysis, business model, MBM scores.
5. Recreation — CapCut / InVideo / Canva / Midjourney / Flux / ChatGPT / Claude / Gemini prompts.
6. Knowledge layer — duplicate detection, trend detection, creator profiles, weekly reports.
7. Dashboard — local searchable UI (reels, top hooks, trends, MBM scores, weekly reports).
8. GitHub — commit per run, changelog, stats, push after approval.

## Constraints
- Authenticated session only. Cache aggressively. Incremental sync (skip unchanged Reels).
- Local inference preferred (whisper, PaddleOCR, Qwen2.5-VL, BGE-M3, Qwen3/DeepSeek/Llama).
- Integrations: Browser MCP, Chrome DevTools MCP, GitHub, Obsidian/Markdown, SQLite,
  ChromaDB/Qdrant (optional), Ollama, local Whisper, PaddleOCR, FFmpeg.

## Output Contract (per run)
```
status: success | failure | skipped
reels_processed: int
new_reels: int
skipped: int
databases_updated: [...]
reports: [...]
errors: [...]
next_action: string
owner: "system" | "human"
timestamp: ISO8601
```
