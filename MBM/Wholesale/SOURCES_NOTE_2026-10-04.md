# Sources note — DFW distressed-homeowner research, 2026-10-04

Research-only pull for the wholesaling blitz. Nothing sent. All data compiled into
`~/workspace/wholesale_blitz/raw_auction_list_2026-10-04.json` (66 records: 37 full addresses, 29 partial-street only).

## Source yield summary

| Source | URL | Yielded | Details |
|---|---|---|---|
| Xome (Auction.com group) — Dallas auction list | https://www.xome.com/auctions/listing/TX/Dallas | **10 full addresses** | "Foreclosure Homes" + Non-Bank Owned, cash-only, in-person/online bidding. Only 1 had a starting bid ($130k). Fetched fresh 2026-10-04. |
| Xome — Texas auction list | https://www.xome.com/auctions/tx | **8 full addresses** (Tarrant: Fort Worth ×3, Arlington, Azle, Richland Hills, River Oaks, Mansfield) | 2nd-Chance Foreclosure (CWCOT) starting bids + reserves; Non-Bank Owned starting bids. Fetched fresh 2026-10-04. |
| Xome — older search-engine crawls | same URLs | **8 full addresses** (Dallas: Rowlett ×3, Cedar Hill, Hutchins; Tarrant: Bedford, Arlington ×2, Fort Worth) | Crawls from ~2026-09-16 / ~2026-09-30. Not re-verified live — flag as "verify still listed". |
| Texas Signals — Dallas County | https://texassignals.com/auctions/dallas | **6 full addresses** | From the free 6-of-645 sample (fetched 2026-10-03). Auction date 2026-10-06 (Oct sale, 2 days out). Assessed values where published. |
| Texas Signals — Tarrant County | https://texassignals.com/auctions/tarrant | **5 full addresses** | Free 6-of-353 sample. Auction date 2026-10-06, assessed values published. |
| foreclosurelistings.com | https://www.foreclosurelistings.com/ | **29 partial addresses (street only)** — 17 Dallas, 12 Fort Worth | Pre-foreclosures with est. values, beds/baths/sqft. House numbers hidden behind login ("View Address"). Flagged `address_partial: true`. |

## Blocked / limited sources

- **Texas Signals full lists** — confirmed to hold **244 Dallas + 132 Tarrant postings for the Nov 3, 2026 sale**, but full addresses require an email signup (free) or 7-day trial. Could not unlock without a browser session / email address. This is the single biggest unlock available for the Nov 3 cycle.
- **Dallas County Clerk public search (dallas.tx.publicsearch.us)** — interactive JS search portal; notices filed on/after 2026-02-24 require selecting "Foreclosure" in a dropdown form, not fetchable via text fetch. The legacy PDF folders on dallascounty.org only show March/April/May of the previous cycle.
- **Tarrant County** — the ecountyclerk posting pages are old/redirected; current postings live behind a similar interactive portal (not reachable via text fetch).
- **auction.com (auctions.com) Dallas County page** — loaded without property addresses in text (JS-driven); the Xome pages (same corporate group) worked instead.
- **foreclosurerepos.com** — pre-foreclosure PMV data visible but every address is "Login To View Address". Pre-foreclosures overlap heavily with foreclosurelistings.com; no unique addresses extracted.
- **HUD Homestore / housinglist.com** — listing cards show city/zip/beds only; prices and full addresses require registration.

## Honesty / data-quality notes

- `owner_name`: **null on every record** — no source published owner names publicly. Do not invent.
- `lender` / `lien_amount`: **null on every record** — not published by any open source.
- `auction_date`: set only where the source published it (Texas Signals: 2026-10-06). Null elsewhere.
- Xome "2nd Chance Foreclosure" = CWCOT (Claims Without Conveyance of Title) online auction — not the county courthouse trustee sale. Opening bids are "Starting Bid"; reserves shown in `notes`, not treated as valuations.
- Partial-address records (29) have street name, city, zip, est. value — usable for street-level sweep / skip tracing, NOT for direct mail without enrichment.
- County assignment: city/zip-based (e.g. Mansfield 76063 spans counties — flagged in record notes).
- No November 3, 2026 postings were extractable individually from any free source; the actionable lane for Nov 3 is the Texas Signals free-list signup or the county clerk portals via a live browser session.
