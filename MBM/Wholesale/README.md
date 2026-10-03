# MBM/Wholesale — Wholesaling Operation

Docs for the wholesale deal operation: how we call distressed sellers and what
deals are on the board.

## Files

| File | What |
|---|---|
| `COLD_CALL_SCRIPT.md` | Cold-call scripts (owner-occupied, LLC, RE pro) + objection handling + after-call checklist |
| `DEALS_2026-07-07.md` | Deal sheet for the Aug 4, 2026 auction cycle — 20 DFW properties, cash-buyer table, owner contacts |

## Related

- Assignment agreement form: `../LeadEngine/contracts/` (executed examples; the
  AS-IS cash assignment form used on deals)
- Buyer matching / disposition engines: `../LeadEngine/buyer_matching_engine.py`,
  `../LeadEngine/buyer_buy_box_engine.py`, `../LeadEngine/ad_disposition.py`

## Status

The fresh deal sheet covers the **Nov 3, 2026 auction cycle** (`DEALS_2026-10-04.md`,
generated 2026-10-04). Fresh pull: **66 raw leads** → **65 survived filtration**
(37 full-address, 28 partial street-only, 1 junk killed). 19 have computable
40%-of-asking cash offers; 18 full-address need comp research; 28 partials need
house-number enrichment. Owner names: **all REQUIRES_VERIFICATION** (DCAD
unreachable from this environment; Tarrant ArcGIS layer holds county-owned
parcels only). Phones: **none verified** — skip-trace blocked until owner names
resolve. SMS sending blocked until Phound is provisioned.

**Founder actions to unblock:** (1) free Texas Signals signup → 244 Dallas +
132 Tarrant Nov-3 postings with house numbers + owners; (2) provision Phound;
(3) resolve owner names via dallascad.org/tad.org for Tier 1 addresses.

The Aug 4, 2026 cycle (`DEALS_2026-07-07.md`) is archived for reference.
Before the next cycle: open a fresh deal sheet, run every owner phone through
skip-trace verification (`../LeadEngine/seller_skip_tracer.py`), and scrub the
call list against DNC/TCPA before dialing.
