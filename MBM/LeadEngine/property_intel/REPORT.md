# JARVIS WORKER 2 — Issue #23 Data Side: Implementation Report

> **Owner:** jarvis-worker-2 · **Date:** 2026-08-15 · **Scope:** DATA side of
> `MohammedAbdelshafy/jarvis-mbm#23` ("MBM Property Intelligence + Owner
> Verification + Lead Ranking Engine v2") — the platform/UI side is Worker 1.

## Deliverables

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| A | **Fresh Auction.com property pipeline** — `property_intel/auction_freshness.py` | ✅ built; live source BLOCKED | Live scrape → `{"blocked": true}` (Imperva/Incapsula HTML captured). File ingestion + freshness scoring fully tested. |
| B | **Authoritative county ownership verification** — `ownership_verifier.py` + `county_sources.py` + `COUNTY_SOURCES.md` | ✅ built + live-verified for Dallas (DCAD) | 2026-08-15 live: `12124 Schroeder Rd, Dallas` → VERIFIED owner `CHANDLER TAMECA`, parcel `00000719884000000`. Harris ambiguous → CONFLICT (correct). |
| C | **Business-owner AI-services prospect lane** — `business_prospector.py` | ✅ built; live RapidAPI 429 | Offline scoring verified on sample rows (5/5 prospects). Live quota exhausted → reported, never fabricated. |
| D | **Scoring + ranking engine with reason traces** — `scoring.py`, `pipeline.py` | ✅ built + live slice | Vertical slice: 3/3 records VERIFIED (100%), ranked with per-component reason traces. |
| E | **Tests** — `property_intel/tests/` | ✅ **83 passed** (hermetic, no network) | `python -m pytest property_intel/tests -q` → 83 passed in 2.2s. |
| F | **npm scripts + AGENTS.md** | ✅ | `leads:prop`, `leads:prop:live`, `leads:prop:test`, `leads:auction*`, `leads:biz*`. |

## Live verification results (2026-08-15)

| Endpoint | Latency | Result |
|---|---|---|
| **DCAD (Dallas)** — `maps.dcad.org/.../ParcelQuery/MapServer/4` | 2.5–4.7 s | **VERIFIED** — real owners + APN |
| **Tarrant** — `mapit.tarrantcounty.com/.../TCProperty/MapServer/0` | 3–6 s | Reachable; NOT_FOUND for sample address |
| **Harris (HCAD)** — `www.gis.hctx.net/.../HCAD/Parcels/MapServer/0` | 6–12 s | Reachable; **CONFLICT** (5 distinct owners @ "1300 MAIN") — correct, no owner asserted |
| **Collin (CCAD)** — `gismaps.cityofallen.org/...` | ~24 s | Reachable; NOT_FOUND (slow, query tuning needed) |
| **Auction.com** | 15 s timeout | **BLOCKED** by Incapsula/Imperva bot protection |
| **RapidAPI Google Maps** | immediate | **HTTP 429** (quota exhausted) |

## Integrity behavior (issue #23 hard rules)

1. **Owners are never guessed.** Only `VERIFIED` (unique, high-match) and
   `LIKELY` (single candidate, partial match) assert an owner; ambiguous matches
   return `CONFLICT` with an empty owner field.
2. **No fabricated auction data.** Blocked scrape → empty result + diagnostic;
   the old `auction_scraper.py` mock-fallback pattern is not carried forward.
3. **No fabricated phones/contacts.** A lead without a real phone/owner is
   hard-capped `callability ≤ 39` and never enters the prime queue
   (`PRIME_QUEUE_CALLABILITY = 50`).
4. **Negative dispositions suppress recycling.** `BAD_NUMBER`/`WRONG_PERSON`/
   `NON_OWNER`/`DNC` cap callability so garbage is not recycled.
5. **Provenance everywhere** — `source`, `source_url`, `source_date`,
   `retrieved_at`, `verification_status`, `confidence` on every assertion.

## Vertical slice (live, sample fixture)

```
ingested 3 → normalized 3 → routed 3 → verified 3/3 (100%)
3134 Arizona Ave   → HARMON PROPERTY SERVICES LLC   [VERIFIED] opp=69 call=39 combined=57
12124 Schroeder Rd → CHANDLER TAMECA               [VERIFIED] opp=62 call=39 combined=53
1510 Glen Ave      → HARMON PPTY SVCS LLC          [VERIFIED] opp=61 call=39 combined=52
prime_queue=0 (correct — no phone, no history → never fabricate callability)
```

## Blockers handed to platform side

- **Auction.com** requires an authorized session/proxy or official data channel
  (bot protection). Pipeline, freshness scoring, and file ingestion are ready;
  the live fetch is the only missing link.
- **RapidAPI Google Maps** quota (429) — replenish or swap to another authorized
  business-data provider; the adapter interface accepts any.
- **Tarrant / Harris / Collin** endpoints are usable but slow; Harris needs an
  APN to reach VERIFIED (address alone is ambiguous by nature of HCAD data).
- **Supabase tables** (properties, parcels, owners, auctions, evidence,
  lead_scores) do not exist yet — schema shapes are in `schema.py` and emitted
  in artifacts; DB wiring is Worker 1 / platform work.

## File inventory (new)

`MBM/LeadEngine/property_intel/` — `__init__.py`, `schema.py`, `normalize.py`,
`county_sources.py`, `county_registry.py`, `ownership_verifier.py`,
`auction_freshness.py`, `scoring.py`, `business_prospector.py`, `pipeline.py`,
`COUNTY_SOURCES.md`, `README.md`, `samples/sample_auction_records.json`,
`samples/sample_business_rows.json`, `tests/` (83 tests), `artifacts/`,
`reports/`.

Root: `package.json` gained `leads:prop*`, `leads:auction*`, `leads:biz*` scripts.