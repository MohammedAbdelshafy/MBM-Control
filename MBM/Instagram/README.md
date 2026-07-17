# MBM Instagram Intelligence System

Turn your own authenticated Instagram account into a searchable, structured
intelligence database built from Saved / Liked / Collection / Following / Explore
Reels. Operates ONLY within content your logged-in account can legitimately view.
Never bypasses auth or accesses private data. Respects Instagram ToS.

## Layout
```
MBM/Instagram/
  MISSION.md            mission brief
  SOP.md                operating procedure (auth-only, incremental, local-first)
  TEMPLATE.md           per-Reel Markdown schema (all analysis fields)
  config.example.yaml   safe defaults
  config.local.yaml     YOUR local config (gitignored)
  requirements.txt      python deps (local-first inference)
  ig_intel/             the package
    schema.py           Reel model, hashing, Markdown renderer, SQLite DDL
    db.py               DB layer (7 SQLite DBs) + detail-row insertion
    config.py           config loader
    collector.py        browser collector (chrome-devtools MCP | Playwright)
    media.py            FFmpeg download / audio / frame sampling
    analysis.py         speech(OCR)+vision(VLM)+LLM classification
    knowledge.py        duplicates, trends, creator profiles, weekly report
    run.py              orchestrator + per-run Git commit + output contract
    dashboard.py        static dashboard generator + local server
    __main__.py         CLI: run | demo | dashboard
```

## Setup
```powershell
cd MBM/Instagram
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# optional local models
ollama pull qwen2.5-vl
ollama pull qwen3
cp config.example.yaml config.local.yaml   # then edit
```

## Authenticated browser (required for `run`)
Start Chrome already logged into Instagram with remote debugging:
```powershell
# find your chrome path; example:
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
   --remote-debugging-port=9222 `
   --user-data-dir="$env:USERPROFILE\AppData\Local\Chrome-IG-Profile"
```
Then open Instagram and confirm you're logged in. The collector reads only what
that session can view. (Playwright fallback: set `playwright_profile` to a
logged-in profile path instead.)

## Run
```powershell
python -m ig_intel run --config config.local.yaml
```
Per Reel it: collects metadata -> downloads media (if a video/thumbnail URL is
available) -> transcribes (whisper) -> OCR (PaddleOCR) -> vision analysis
(qwen2.5-vl) -> LLM classification (qwen3) producing all scores + recreation
prompts -> writes a Markdown file under `Knowledge/Instagram/<niche>/` -> upserts
into the 7 SQLite DBs -> builds creator profiles / trends / weekly report ->
commits to Git (push only after your approval via config `git.auto_push`).

Any missing local engine is skipped gracefully (the Reel is still stored with
whatever was extracted), so the run never hard-fails on a missing model.

## Dashboard
```powershell
python -m ig_intel dashboard --config config.local.yaml --port 8787
```
Generates `Knowledge/Instagram/dashboard.html` and serves it at
http://127.0.0.1:8787/ with search, niche/model filters, top hooks/niches, and
creators. Use `--no-serve` to only write the file.

## Offline self-test
```powershell
python -m ig_intel demo
```

## Output contract (per run)
```
status, reels_processed, new_reels, skipped, databases_updated,
reports, errors, next_action, owner, timestamp
```
