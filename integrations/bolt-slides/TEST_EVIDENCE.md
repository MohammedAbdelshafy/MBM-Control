# TEST EVIDENCE — bolt-slides (VibeFounder power #8)

**Date:** 2026-10-09 | **Run:** `vibefounder-night-shift` | **Command:** `python3 test_smoke.py`
**Result: 11/11 PASS** — hermetic (in-process rendering + MCP server over
stdio subprocess; no network, no keys, no browser).

```
PASS test_escape_xss — <script>/<img onerror>/<b> payloads render escaped, never raw
PASS test_cover_and_bullets_render — cover + click-to-reveal bullets render, 2 slides
PASS test_widgets_present — dcClean() + roiUpdate() JS and widget markers present
PASS test_keyboard_and_nav_js — ArrowRight/Left, build-reveal, notes toggle, fullscreen, progress/counter; no external URLs
PASS test_chart_validation — negative / non-numeric / empty series rejected
PASS test_bad_inputs_rejected — empty title, bad theme, unknown widget, empty bullets, bad tier, empty CTA URL
PASS test_json_roundtrip — to_dict() is JSON-serialisable with kinds intact
PASS test_export_file — writes <!DOCTYPE html> … </html>, correct <title>
PASS test_sample_builds — 8-slide DataClean pitch: cover/bullets/widget/statement/widget/chart/pricing/cta
PASS test_sample_cli — --sample writes samples/dataclean-pitch.html (15,020 bytes)
PASS test_full_flow_over_stdio — initialize → 6 tools → create/add/get/list/export/render; bad kind, bad deck_id, unknown tool all return isError inside the protocol
```

What each test proves:

| # | Test | Proves |
|---|---|---|
| 1 | escape_xss | prospect/pasted content can't break out of the deck (XSS-safe) |
| 2 | cover_and_bullets_render | core slide kinds render with correct structure |
| 3 | widgets_present | the actual "live apps inside slides" power ships in the HTML |
| 4 | keyboard_and_nav_js | presentation UX works: nav, builds, notes, fullscreen, deep-links |
| 5–6 | chart_validation, bad_inputs_rejected | bad specs fail fast with clear errors, not broken decks |
| 7 | json_roundtrip | decks are portable JSON (MCP-safe) |
| 8 | export_file | one self-contained file, emailable/presentable anywhere |
| 9–10 | sample_builds, sample_cli | the DataClean $499 pitch deck generates end-to-end |
| 11 | full_flow_over_stdio | the MCP server speaks real JSON-RPC 2.0 and all 6 tools work |

Honest limits: rendering is validated structurally, not visually — no
browser screenshot was taken on this headless VM. The in-page demo JS
(`dcClean`, `roiUpdate`) is shipped unexecuted here; logic mirrors the
tested Python-side contracts (escaping, markers, config plumbing).
