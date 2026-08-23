# Daily Lead Ingestion Report — daily-ingest-20260823T125955-100

- **Status:** `SUCCESS` (apply)
- **Source:** `npi_verified_callsheet.json@2026-08-23T11:55:59.239638+00:00`
- **Started:** 2026-08-23T12:59:55.899340+00:00  |  **Completed:** 2026-08-23T13:00:16.266038+00:00

| Metric | Count |
|---|---|
| Raw | 2388 |
| Accepted | 0 |
| New | 0 |
| Duplicates | 2306 |
| Suppressed | 21 |
| Rejected | 61 |
| Needs review | 0 |

- **Canonical:** before=4484 after=4484 revision=34->35
- **Dataset hash:** `03fffea9af850bb9…`
- **Script coverage:** 100.0%  |  **Segment coverage:** 100.0%
- **Live verified:** YES

## Stage Pipeline

| Stage | Completed | Detail |
|---|---|---|
| source_fetch | YES | 2388 rows from npi_verified_callsheet.json@2026-08-23T11:55:59.239638+00:00 |
| raw_ingest | YES | 2385 structured candidates (3 malformed dropped) |
| phone_identity_validation | YES | US phone + identity gate applied to every candidate |
| provenance_validation | YES | LeadProvenanceGate applied to every candidate |
| synthetic_check | YES | strong synthetic fingerprint veto applied |
| dedupe | YES | 2306 duplicates (115 enriched via history-preserving merge) |
| suppression_dnc_check | YES | 21 suppressed/DNC (suppression index size 102) |
| classification | YES | 0 NEEDS_REVIEW; segments=[] |
| script_assignment | YES | coverage 100.0% (canonical script engine) |
| canonical_write | YES | 0 new + 115 merged committed (total 4484) |
| revision_audit | YES | revision 34 -> 35; audit=ok |
| queue_prioritization | YES | 0 new leads promoted newest-first; call_now page=25 |
| live_verification | YES | counts match + samples traced + UI serving |
## Day Rollup (all runs)

| Run | Status | Raw | New | Dupes | Suppressed | Rejected | Needs review |
|---|---|---|---|---|---|---|---|
| `7-2000` | SUCCESS | 2388 | 1339 | 975 | 13 | 61 | 0 |
| `55-100` | SUCCESS | 2388 | 0 | 2306 | 21 | 61 | 0 |

**Day totals:** raw=4776, new=1339, duplicates=3281, suppressed=34, rejected=122, needs_review=0