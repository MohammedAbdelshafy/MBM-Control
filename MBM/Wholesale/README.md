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

The current deal sheet covers the **Aug 4, 2026 auction cycle** (now past).
Before the next cycle: open a fresh deal sheet, run every owner phone through
skip-trace verification (`../LeadEngine/seller_skip_tracer.py`), and scrub the
call list against DNC/TCPA before dialing.
