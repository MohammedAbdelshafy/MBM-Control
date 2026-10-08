# bolt-slides — interactive pitch decks with live demo widgets

**VibeFounder power #8:** *"Generate interactive presentations with live apps
inside"* ([Bolt.new Slides reel](https://www.instagram.com/reel/Da3DxB8uKBk/))
→ **DataClean AI / AI Consultancy Sprint** (pitch tooling).

Proposals that demo a live ROI calculator close better than PDFs. This
integration is a stdlib-only deck generator (Python) that emits **one
self-contained HTML file** per deck — no npm, no build step, no CDN, no
network needed at presentation time. The "live apps inside" are real
interactive widgets embedded in slides:

| Widget | What it does |
|---|---|
| `data_clean_demo` | "Messy list → clean list" live demo: paste rows, hit the button, dedupe + normalise + lowercase + phone-scrub runs 100% in-page |
| `roi_calculator` | Prospect-tunable sliders (hours/week, hourly value, team size) computing *their own* manual-cleaning cost and pilot payback |

Pattern credit: [Bolt Slides](https://github.com/stackblitz/bolt-slides)
(open-source) proved the "slides are a web app" pattern — click-to-reveal
builds, presenter notes, live components. This is a clean-room stdlib
reimplementation tuned for sales decks, not a fork.

## Layout

| File | What |
|---|---|
| `deck_builder.py` | deck model + single-file HTML renderer + CLI |
| `mcp_server.py` | stdlib MCP stdio server (6 tools) |
| `test_smoke.py` | 11 hermetic tests — no network, no keys |
| `samples/dataclean-pitch.html` | generated DataClean AI $499 pitch (8 slides) |
| `SKILL.md` | reusable skill doc |
| `WIRING.md` | where this plugs into the founder's products |
| `TEST_EVIDENCE.md` | test results |

## Quickstart

```bash
# 1. Generate the sample DataClean AI pitch deck:
python3 deck_builder.py --sample
# → samples/dataclean-pitch.html — open it in any browser, present with F

# 2. Build your own deck in Python:
python3 - <<'EOF'
from deck_builder import Deck
d = Deck("Acme — Pilot Pitch", theme="midnight")
d.add_cover(kicker="ACME", title="We fix your list.",
            subtitle="48-hour turnaround.", cta="keep clicking ↓")
d.add_bullets("The problem", ["dirty data", "wasted spend"])
d.add_widget("roi_calculator", title="Price your own pain",
             config={"pilot_price": 499})
d.add_cta("Start free", ["Send any messy list."],
          "Start my free sample →", "https://clipform.io/7f9689f00")
d.save("acme-pitch.html")
EOF

# 3. Present: ←/→ or click to advance, N = presenter notes, F = fullscreen
```

## Slide kinds

`cover` (kicker/title/subtitle/cta) · `bullets` (click-to-reveal items) ·
`statement` (big headline + sub) · `widget` (`data_clean_demo` |
`roi_calculator`) · `chart` (SVG bars) · `pricing` (tier cards) ·
`cta` (headline + lines + button). Every slide takes presenter `notes`.

## MCP tools

`deck_create`, `deck_add_slide`, `deck_get`, `deck_list`,
`deck_export_html`, `deck_render_html`.

Wire-up (Claude Code / Cursor):

```json
{"mcpServers": {"bolt-slides": {
    "command": "python3",
    "args": ["<abs path>/mcp_server.py"]}}}
```

## Honest limits

- Decks are **static single files** — the demo widgets run in-page JS;
  there is no backend and no real cleaning happens on the prospect's data.
- The ROI calculator computes from **the prospect's own slider inputs**;
  it is a calculator, not a promise. Never present its output as our claim.
- The sample deck's chart is labelled illustrative on the call — say so.
- All user content is HTML-escaped at render; widget config reaches JS
  only via `json.dumps`.
