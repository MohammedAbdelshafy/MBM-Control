# Skill: bolt-slides (interactive pitch decks)

Build interactive, single-file HTML pitch decks with **live demo widgets
inside the slides** — the VibeFounder power #8 pattern ("proposals that
demo a live calculator close better than PDFs").

## When to use

- A sales call needs more than a PDF: DataClean AI $499 pitch, AI
  Consultancy Sprint pitch, any Whop product walkthrough.
- You want the prospect to *touch* the product mid-pitch (clean a sample
  list, drag ROI sliders) instead of reading claims about it.

## Build a deck (Python API)

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/bolt-slides")
from deck_builder import Deck

d = Deck("DataClean AI — $499 Pilot", theme="midnight")  # or "paper"
d.add_cover(kicker="MBM · DataClean AI",
            title="Your list is costing you money.",
            subtitle="10,000 records in 48 hours.",
            cta="keep clicking — live demo inside ↓",
            notes="Open with pain, not the pitch.")
d.add_bullets("Dirty data is a silent tax",
              ["Duplicate leads → double calls",
               "Dead emails → sender reputation damage"],
              notes="One click per bullet.")
d.add_widget("data_clean_demo", title="Watch it work — live",
             notes="Runs in-page. Offer to paste THEIR sample list.")
d.add_widget("roi_calculator", title="Price your own pain",
             config={"hours_per_week": 6, "hourly_value": 50,
                     "team_size": 2, "pilot_price": 499})
d.add_chart("What you get back",
            [("Duplicates removed", 18), ("Bad emails fixed", 24)])
d.add_pricing("Start free. Scale when it works.",
              [{"name": "Free sample", "price": "$0",
                "features": ["500–1,000 records", "48-hour process"]},
               {"name": "$499 Pilot", "price": "$499",
                "features": ["Up to 10,000 records", "48-hour turnaround"],
                "highlight": True}])
d.add_cta("Get your free sample", ["Send any messy list."],
          "Start my free sample →", "https://clipform.io/7f9689f00")
d.save("pitch.html")   # one self-contained file — email it, present it
```

## Slide-kind payload reference (also the MCP `deck_add_slide` schema)

| kind | payload fields |
|---|---|
| `cover` | `kicker`, `title`, `subtitle`, `cta` |
| `bullets` | `title`, `items[]` (click-to-reveal, one per click) |
| `statement` | `text`, `sub` |
| `widget` | `widget`: `data_clean_demo` \| `roi_calculator`, `title`, `config{}` |
| `chart` | `title`, `series`: `[[label, value], …]` (non-negative numbers) |
| `pricing` | `title`, `tiers[]`: `{name, price, features[], highlight?}` |
| `cta` | `title`, `lines[]`, `button_text`, `button_url` |

All kinds accept `notes` (presenter notes — press **N** while presenting).

Widget configs: `data_clean_demo` takes `heading`, `sample` (preloaded
messy rows); `roi_calculator` takes `heading`, `hours_per_week`,
`hourly_value`, `team_size`, `pilot_price`.

## Present

Open the HTML file → `←`/`→` or click advances (bullets reveal one per
click first) → `N` toggles presenter notes → `F` fullscreen → `#s3`
deep-links to slide 3.

## MCP tools

`deck_create`, `deck_add_slide`, `deck_get`, `deck_list`,
`deck_export_html`, `deck_render_html`. Decks live in server memory;
export to keep.

## Auth / config

None. No API keys, no network, no build tools. Python 3.8+ stdlib only.

## Operating rules

1. **The demo is illustrative, the calculator is theirs.** The
   `data_clean_demo` runs toy logic in-page; the ROI math uses the
   prospect's own slider inputs. Never present either as measured
   customer results.
2. **Outbound copy rules still apply:** quantified operating proof only,
   never customer ROI; single $499 pilot offer; opt-out on emails that
   link a deck.
3. **One file per pitch** — `deck_export_html` to a named file, send the
   file or present live. Don't regenerate mid-call.
4. **Escape is automatic** — all content is HTML-escaped; never bypass it
   to inject raw HTML.
5. Keep decks honest: label the sample chart "illustrative" on the call;
   the close is always the **free 500-record sample**, not the $499.
