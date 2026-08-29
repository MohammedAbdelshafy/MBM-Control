# Supply Expansion Evaluation — Legitimate Property Sources
**Date:** 2026-08-29T21:30+03:00
**Baseline:** 57 DCAD sellers, 48 enriched (84.2% yield) via owner-name ParcelQuery

## Evaluated Sources

| Source | Coverage | Freshness | Field Quality | Property Yield | Owner Yield | Phone Yield | Cost | Legal/Terms | Failure Modes |
|---|---|---|---|---|---|---|---:|---|---|
| **DCAD ParcelQuery MapServer/4** (maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4) | Dallas County only (1 county) | Real-time tax roll (daily) | SITEADDRESS, PARCELID, OWNERNME1/2, PSTLADDRESS (no listing status, no distress signals) | **84.2%** (48/57 owner-name queries returned valid parcel) | 84.2% (same) | 100% (phones already NPI-verified) | Free, no key | Public records, allowed | `no feat` for 9 (name mismatch: "Whittenburg Joshua M. & Emily S." with ampersand, "Dean Nola J." with middle, LLC suffix variations); requires exact owner string; 1-2s latency; `exceededTransferLimit` on broad queries |
| **Tarrant/Harris/Collin ArcGIS** (county_sources.py registry) | Tarrant, Harris, Collin (verified endpoints) | Real-time but slower (3-24s per property_intel/README.md:92) | Same fields, Harris often CONFLICT without APN | Not tested live (conservative, Harris CONFLICT) | Not tested | 100% if phone present | Free | Public, allowed | Tarrant/Harris slower, Harris ambiguous → CONFLICT, needs APN |
| **Auction.com** (auction_freshness.py) | National, Dallas County listings sample_auction_records.json:3 | Freshness scoring (auction_date) | address, auction_status, opening_bid, estimated_value, occupancy_signal | Dry-run 100% (3/3), live **BLOCKED by Imperva/Incapsula** per README:90 | 0 live (blocked) | 0 | Free but bot-protected | Requires anti-bot proxy or official channel; bypass not allowed |
| **RapidAPI Google Maps** (business_prospector.py) | National business search | Real-time | business phone, place_id | Offline 100% (FileBusinessSource), live **429 quota** per README:92 | N/A | 100% offline (555 fixtures, not real) | Paid (RAPIDAPI_KEY) | Allowed but quota hit |
| **Assessor/Recorder/Tax Delinquency/Code/Municipal/Probate** | County-specific, legally accessible public records | Varies (tax annual, code violation as reported, probate court records) | Requires per-county scraper + legal review for probate | Not yet implemented | — | — | Free (court sites) | Must ensure licensing/terms allow this use; probate where legally accessible only |
| **Approved Property Data Providers** (ATTOM, PropStream licensed) | National, richer fields (equity, tenure, vacancy, lien) | Daily/weekly | High (signals, AV​M, lien) | Not evaluated (no licensed key) | High | High (skip trace) | Paid | Requires approved data license — not used; would violate if scraping around controls |

## Recommendation: Strongest Legitimate Source

**Primary:** **DCAD ParcelQuery (Dallas County)** — proven 84% property yield on existing inventory, free, public, immediate, no CAPTCHA, legal, + NPI phone verification already gives 100% phone yield. For Dallas-centric acquisition lane, this is the strongest.

**Expansion path (legitimate, scalable beyond Dallas):**
1. **County-by-county ArcGIS registry** (`MBM/LeadEngine/property_intel/county_sources.py:county_registry.py`) — route each property to its authoritative county endpoint (already researched). Prioritize Dallas → Tarrant → Collin (all DFW), then Harris with APN-first to avoid CONFLICT.
2. **Tax delinquency rolls** where the county publishes a separate delinquency list (not scraped around anti-bot) — join to parcel to get high-equity + tax signal without inferring distress.
3. **Licensed provider only after legal review** — ATTOM or similar approved channel for nationwide expansion with proper terms (costed, field quality high, but requires contract).

**Not chosen:** Auction.com live scrape (blocked, would require bypassing Incapsula — not allowed), RapidAPI without quota upgrade (429), any scraper that bypasses CAPTCHA/anti-bot (prohibited).

## Property-First Yield Evidence (Live Run 2026-08-29)
- Input: 57 DCAD sellers (source_type `COUNTY_PROPERTY_TAX_ROLL`)
- Method: `UPPER(OWNERNME1) LIKE '%owner%' OR OWNERNME2` via `ParcelQuery/MapServer/4` (maps.dcad.org)
- Result: 48 enriched with `SITEADDRESS + PARCELID + PSTLADDRESS` → `property_evidence:PRESENT`, `PARCELID` as source_reference, `retrieved_at:now()`, `listing_status:UNKNOWN`, `off_market_status:UNKNOWN` (honest), `callable:true` if phone_verified
- Yields: Property 84.2% (48/57), Owner 84.2% (same), Phone 100% (already verified), Cost $0, Legal: public records
- Failure modes: 9 no feat (ampersand names, middle initials, generic "Global Integrity Construction" not owning Dallas parcel) — correctly marked UNKNOWN, not fabricated.

## Next Scalable Ingestion Design
```
New Auction/Assessor record (address+APN)
 → normalize (normalize.py) → dedupe (dedupe_records)
 → county_registry.route_property → DCAD/Harris/Tarrant verified endpoint
 → ownership_verifier.verify_ownership (APN exact or address score ≥4.0 → VERIFIED else CONFLICT/NOT_FOUND; caller handles CONFLICT)
 → provenance (source, source_url, source_date, retrieved_at, confidence)
 → scoring (scoring.py: opportunity + callability with trace)
 → gate (PRIME_QUEUE_CALLABILITY 50 + ownership VERIFIED/LIKELY + phone present)
 → queue (dialer_queue_engine.rank_main_queue → FRESH_CALL_NOW/NEXT)
 → script (property-specific when evidence exists, no distress claim)
 → Phound handoff
```
No network call or artifact write unless `--verify-live --apply` (pipeline.py:6).

**Chosen for production:** Continue Dallas DCAD live enrichment for existing 135 → then ingest new Dallas parcels via assessor/auction sample fixture → live verify → expand to Tarrant/Collin via same county registry. Do not expand to Harris without APN-first (to avoid CONFLICT waste).

