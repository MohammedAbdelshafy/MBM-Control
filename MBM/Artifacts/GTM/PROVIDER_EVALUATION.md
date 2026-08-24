# SKIP-TRACE PROVIDER EVALUATION & BENCHMARK PROTOCOL v1.0

> Owner: OX ALPHA · Status: RESEARCH COMPLETE / INTEGRATION BLOCKED ON CREDENTIALS
> Law: no provider is trusted on marketing claims. Only measured benchmark +
> live scoreboard results drive selection.

---

## 1. Provider Research Matrix

| Criterion | PropStream | DealMachine | Batch SkipTracing | Twilio Lookup | RapidAPI skip-trace listings |
|---|---|---|---|---|---|
| Owner match evidence | parcel+titled owner | parcel+owner | name/address match | phone intelligence only | varies by listing |
| Phone match rate | vendor-claimed ~60-90% (UNVERIFIED) | vendor-claimed (UNVERIFIED) | vendor-claimed up to 90%+ (UNVERIFIED) | n/a (validates, not finds) | unknown per listing |
| Mobile/line-type | yes | yes | yes | yes (line-type intelligence) | sometimes |
| DNC flag | partial (federal) | partial | often offered add-on | no (identity data only) | rarely |
| Litigator flag | no | no | some vendors offer | no | rare |
| API access | REST (paid tiers) | REST | REST/batch upload | REST (Lookup product; MBM account returned 401 - product not enabled) | REST |
| Batch support | exports | exports | bulk lists | per-number | varies |
| Price model | subscription + per-skip bundles | subscription + credits | per-record (~$0.15-0.25 claimed) | per-lookup (~$0.008-0.05) | per-call |
| Latency | seconds-bulk | seconds | minutes-hours batch | real-time | real-time |
| Coverage | US property-centric | US property-centric | US person-centric | global telephony | US-heavy |
| Provenance quality | source labels vary | limited | limited | carrier-grade for phone facts | undocumented |
| Legal posture | licensed use terms | licensed | FCRA-sensitive; verify permissible purpose | carrier data terms | per-listing ToS |

**Status of every cell above containing "claimed"/"unknown": UNVERIFIED until the §2 benchmark runs.**

## 2. Benchmark Protocol (ready to execute when credentials exist)

Cohort: **100 seller records already in canonical DB**, split:
- KNOWN_GOOD (n≈20): prior CONNECTED_OWNER outcomes with matching names
- KNOWN_BAD (n≈20): the quarantined ID-derived synthetics (ground truth = wrong)
- UNKNOWN (n≈60): DCAD parcel-verified owners lacking phone evidence

Per provider, submit identical cohort; measure:

| Metric | Definition |
|---|---|
| OWNER_MATCH_RATE | returned contacts matching titled owner name ≥ fuzzy-threshold |
| CORRECT_PHONE_RATE | known-good numbers returned correctly; known-bad NOT returned |
| WRONG_PARTY_RATE | returns linked to non-owner persons |
| NO_MATCH_RATE | empty returns on UNKNOWN cohort |
| BAD_PHONE_RATE | known-bad numbers returned as valid |
| DNC_DETECTION_RATE | flagged vs. ground truth where known |
| COST_PER_VERIFIED_CONTACT | spend ÷ contacts passing identity gate |

Decision rule: provider qualifies if `CORRECT_PHONE_RATE ≥ 0.8` AND `WRONG_PARTY_RATE ≤ 0.1`
on KNOWN_GOOD/KNOWN_BAD arms, then UNKNOWN-arm owner-match decides primary vs secondary.

## 3. Integration Contract (already implemented)

`PhoneCandidate(owner_match, address_match, sources[], line_type,
last_verified_at, source_reliability, dnc, litigator, suppressed)` feeds
`score_candidates_with_identity()` → consensus ranking with mandatory
identity-link requirement and disagreement→NEEDS_REVIEW.

## 4. Current Live Posture (honest)

- No paid provider connected. Existing verified evidence: CMS NPI registry,
  DCAD county parcel rolls, official websites.
- Seller lane CALL_READY population: **0 records pending identity evidence**
  (by design — the gate refuses unproven owner<->phone links).
- Healthcare/B2B lanes retain registry-anchored business phones (business
  identity = entity itself), which is a different, lower-risk contact class.
