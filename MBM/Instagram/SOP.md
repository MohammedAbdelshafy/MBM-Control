# Instagram Intelligence — SOP

## 1. Authentication
- Use ONLY the operator's logged-in browser session.
- Preferred: connect `chrome-devtools-mcp` to a running Chrome launched with
  `--remote-debugging-port=9222` (already authenticated).
- Fallback: Playwright-controlled Chrome profile that reuses the operator's cookies.
- NEVER submit credentials programmatically. NEVER attempt to bypass auth.

## 2. Collection (incremental)
- Sources: saved, liked, collections, following feed, explore, specified creators, bookmarks.
- For each Reel capture: url, creator handle, thumbnail, caption, visible metrics, date seen.
- Cache a hash of (url + caption + metrics). Skip Reels whose hash is unchanged.
- Rate-limit: max 1 scroll/2s, max 200 Reels per run unless overridden.

## 3. Media extraction
- Download video to `data/media/< reel_id >.mp4` (only if not cached).
- Extract audio via FFmpeg for transcription.
- Frame samples (1 frame / 2s) for OCR + vision.

## 4. Analysis (local-first)
- Speech: whisper (local) → transcript, summary, key quotes.
- OCR: PaddleOCR on sampled frames → subtitles, overlays, numbers, contacts.
- Vision: Qwen2.5-VL (via Ollama) → scene timeline, editing style, visual breakdown.
- LLM classification (Ollama Qwen3/DeepSeek): hook type, psychology, sales, business model,
  MBM scores, recreation prompts.

## 5. Storage
- One Markdown file per Reel under `Knowledge/Instagram/...` (see TEMPLATE.md).
- Structured rows in SQLite DBs: knowledge.db, creators.db, hooks.db, offers.db,
  psychology.db, editing.db, business_models.db.

## 6. Knowledge layer
- Duplicate detection: same teach-point → merge, link, improve.
- Trend detection: recurring hooks/offers/niches, high-RPM niches.
- Creator profiles: frequency, top topics, avg hook, CTA, offer ladder.
- Weekly report: top 20 hooks / offers / editing styles / niches / opportunities.

## 7. GitHub
- Commit every successful run, organized by date (`instagram/YYYY-MM-DD`).
- Generate CHANGELOG.md + stats. Push only after human approval.

## 8. Safety
- Respect Instagram ToS; do not hammer the endpoint.
- Never store or exfiltrate other users' private data.
- Keep all data local except intentional Git pushes of the operator's own analysis.
