# property_intel — Property Intelligence + Owner Verification + Lead Ranking (jarvis-mbm #23, data side)

The **data side** of GitHub Issue #23: fresh Auction.com opportunity discovery,
**authoritative county ownership verification**, business-owner AI-services
prospecting, and a deterministic scoring/ranking engine with reason traces.

## Hard rules

- **Never invent.** No fabricated owners, phones, contacts, or auction rows.
  A blocked or missing source returns `blocked`/`NOT_FOUND` with diagnostics —
  never mock data.
- **Owner is only who the official source returned.** A person merely
  *associated* with an address is never assumed to be the legal owner.
- **Ambiguity → CONFLICT.** When several distinct owners match the same site
  address, the verifier asserts **no owner** (e.g. HCAD "1300 MAIN" → 5 owners →
  CONFLICT, confidence 0.25).
- **Provenance on every fact.** Each assertion carries `source`,
  `source_url`, `source_date`, `retrieved_at`, `verification_status`, and
  `confidence`.
- **Safe by default.** The pipeline makes no network calls and writes no
  artifacts unless `--verify-live` and `--apply` are passed.

## Modules

| Module | Purpose |
|---|---|
| `schema.py` | Canonical dataclasses + provenance + owner classification |
| `normalize.py` | Lossless address/city/state/county normalization + dedup |
| `county_sources.py` | Registry of official county sources (verified ArcGIS endpoints) |
| `county_registry.py` | Property → county → official source routing |
| `ownership_verifier.py` | Authoritative ownership verification (ArcGIS adapters, CONFLICT-safe) |
| `auction_freshness.py` | Auction.com ingestion (live Playwright scrape or file) + freshness scoring |
| `scoring.py` | Opportunity score + callability score with reason traces + suppression caps |
| `business_prospector.py` | Business-owner AI-services prospect lane (authorized data only) |
| `pipeline.py` | End-to-end vertical slice + report |

See `COUNTY_SOURCES.md` for the researched county registry and live-status
evidence for each endpoint.

## Run (from `MBM/LeadEngine`)

```bash
python -m property_intel.pipeline --source property_intel/samples/sample_auction_records.json            # offline dry-run
python -m property_intel.pipeline --source property_intel/samples/sample_auction_records.json --verify-live --apply   # live verify + write artifacts
python -m property_intel.auction_freshness --state TX --county Dallas --max-pages 2 --debug             # live Auction.com scrape
python -m property_intel.business_prospector --source property_intel/samples/sample_business_rows.json --apply
python -m pytest property_intel/tests -q
```

Or from the repo root:

```bash
npm run leads:prop          # offline pipeline dry-run
npm run leads:prop:live     # live DCAD ownership verify + artifacts
npm run leads:prop:test     # hermetic test suite
npm run leads:auction       # Auction.com freshness (dry-run)
npm run leads:auction:live  # live scrape (blocked by Incapsula — see below)
npm run leads:biz           # business prospector (needs RAPIDAPI_KEY)
npm run leads:biz:file      # offline business scoring on sample rows
```

## Verification flow (ownership_verifier)

1. If the record has a **parcel/APN** → exact APN lookup → single row →
   `VERIFIED` (0.95). Multiple rows → `CONFLICT`.
2. Else **address** lookup: ALL candidates are scored
   (`_address_match_score`: exact 5.0; number+first-word ≥4.0).
   - One distinct owner, score ≥4.0 → `VERIFIED` (0.85–0.95)
   - One distinct owner, score 2–4 → `LIKELY` (0.60)
   - **Multiple distinct owners → `CONFLICT` (no owner asserted)**
   - No candidates → `NOT_FOUND` (0.0)

Every result is annotated onto the property record via `apply_verification()`
(`owner_name`, `ownership_status`, `ownership_confidence`, `ownership_evidence`).

## Scoring (scoring.py)

- **Opportunity** (0–100): distress 25 · equity 20 · vacancy 15 · ownership 10 ·
  fit 10 · recency 8 · contact-confidence 7 · liquidity 5.
- **Callability** (0–100, separate): contact-source 30 · phone 20 · owner-match 20 ·
  recency 15 · prior-success 10 · negatives 5.
- Hard caps: no phone/owner OR a recorded negative disposition
  (`BAD_NUMBER`/`WRONG_PERSON`/`NON_OWNER`/`DNC`) → callability ≤ 39, so garbage
  is never recycled into the prime queue (`PRIME_QUEUE_CALLABILITY = 50`).
- Every score emits `reasons` + a `trace` of `{component, score, weight, reason}`
  explaining WHY a lead ranked where it did.

## Known blockers (documented, not papered over)

- **Auction.com live scrape** is blocked by **Imperva/Incapsula** bot protection
  (debug HTML captured under `artifacts/auction_debug.html`). The scraper returns
  `{"blocked": true, "error": ...}` with no fabricated rows. A session through an
  authorized anti-bot proxy or Auction.com's official data channel is required.
- **RapidAPI Google Maps** returned **HTTP 429** (quota) on the live business
  lane. The adapter reports the error; offline scoring works via
  `--source FILE.json` (`FileBusinessSource`).
- **Tarrant/Harris/Collin ArcGIS endpoints** are slower (~3–24 s) and address
  matching is conservative; Harris commonly yields CONFLICT without an APN.
- **Supabase property tables** (properties/parcels/owners/auctions/evidence/
  lead_scores) do not exist yet — the pipeline emits canonical records and
  artifacts, and the DB dependency is handed off to the platform side.

## License note

Addresses in `samples/sample_auction_records.json` are real Dallas parcels (used
only to validate owner verification); auction dates/bids are illustrative
sample-fixture values and are marked as such. Business sample rows use 555
phone numbers and are explicitly non-sourced fixtures.