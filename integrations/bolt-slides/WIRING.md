# WIRING — bolt-slides into the founder's products

Where this integration plugs in. All wiring points are code-ready
patterns, not live edits — the branch copy lives at
`integrations/bolt-slides/` on `night-shift/vibefounder-powers`.

## 1. DataClean AI $499 pitch — READY TO SEND

`samples/dataclean-pitch.html` is a finished 8-slide deck:

1. Cover — pain-first headline
2. Bullets — dirty-data tax (click-to-reveal)
3. **Live widget** — messy list → clean list demo (paste THEIR rows on the call)
4. Statement — "10,000 records. 48 hours. $499."
5. **Live widget** — ROI slider calculator (their inputs, their math)
6. Chart — shape of a typical clean (label illustrative on the call)
7. Pricing — free sample / $499 pilot / ongoing
8. CTA — free-sample button → https://clipform.io/7f9689f00

**Use it:** attach to the $499 outreach follow-ups, or screen-share on
calls. The close is always the free 500-record sample.

```python
import sys
sys.path.insert(0, "<mbm-control>/integrations/bolt-slides")
from deck_builder import build_dataclean_sample
build_dataclean_sample().save("dataclean-pitch.html")
```

## 2. AI Consultancy Sprint pitch — pattern, 10 minutes

Same skeleton, different numbers: swap the cover/pricing for the
$297 audit / $1,497 sprint / $497-mo tiers, keep both widgets —
`data_clean_demo` becomes "messy ops → clean ops" framing and the ROI
calculator takes `pilot_price: 297`.

## 3. Whop listings + outreach

- Link the deck HTML from Whop product descriptions (direct URL) as the
  "see it work" asset — it needs no backend, so it survives anywhere
  static files are served (GitHub Pages, the public dataclean-ai page).
- Outreach follow-up line: *"I made you a 2-minute interactive pitch —
  there's a live list-cleaning demo inside: <link>"* (opt-out stays on
  the email; the deck itself makes no claims).

## 4. Complements the other night-shift powers

- **higgsfield-video (#4):** embed generated avatar/photoshoot clips as
  a slide's visual once the key exists — slides are plain HTML.
- **swarm-orchestrator (#6):** a "build me a deck for X" task fans out to
  coder agents that call `deck_add_slide` via the MCP server.
- **nvidia-free-models (#1) / ollama-local (#7):** draft slide copy on
  $0/local models, keep the deck assembly here.

## 5. FanForge / ClipOps Studio (later)

The renderer is product-agnostic: FanForge creator pitches and ClipOps
client walkthroughs are the same `Deck` API with different copy. Don't
build a second deck tool — reuse this one.

## Activation checklist

- [x] Nothing to install — stdlib only
- [x] Sample deck generated and verified (`samples/dataclean-pitch.html`)
- [ ] Founder decision: which prospect gets the deck link first
- [ ] Optional: publish the sample deck to GitHub Pages next to the
      DataClean AI landing page for a public "see it work" URL
