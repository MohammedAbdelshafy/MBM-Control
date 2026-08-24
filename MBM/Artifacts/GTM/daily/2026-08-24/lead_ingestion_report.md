# Daily Lead Ingestion Report — daily-ingest-20260824T175732-3900

- **Status:** `FAILED` (apply)
- **Source:** `npi_verified_callsheet.json@2026-08-24T17:55:39.457983+00:00`
- **Started:** 2026-08-24T17:57:32.306343+00:00  |  **Completed:** 2026-08-24T17:58:16.264568+00:00

| Metric | Count |
|---|---|
| Raw | 1415 |
| Accepted | 422 |
| New | 422 |
| Duplicates | 894 |
| Suppressed | 65 |
| Rejected | 34 |
| Needs review | 0 |

- **Canonical:** before=4494 after=4916 revision=39->40
- **Dataset hash:** `498245f92c64d679…`
- **Script coverage:** 100.0%  |  **Segment coverage:** 100.0%
- **Live verified:** NO

## Errors
- live_verification_failed: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>

## Stage Pipeline

| Stage | Completed | Detail |
|---|---|---|
| source_fetch | YES | 1415 rows from npi_verified_callsheet.json@2026-08-24T17:55:39.457983+00:00 |
| raw_ingest | YES | 1415 structured candidates (0 malformed dropped) |
| phone_identity_validation | YES | US phone + identity gate applied to every candidate |
| provenance_validation | YES | LeadProvenanceGate applied to every candidate |
| synthetic_check | YES | strong synthetic fingerprint veto applied |
| dedupe | YES | 894 duplicates (805 enriched via history-preserving merge) |
| suppression_dnc_check | YES | 65 suppressed/DNC (suppression index size 102) |
| classification | YES | 0 NEEDS_REVIEW; segments=['HEALTHCARE_CLINIC'] |
| script_assignment | YES | coverage 100.0% (canonical script engine) |
| canonical_write | YES | 422 new + 805 merged committed (total 4916) |
| revision_audit | YES | revision 39 -> 40; audit=ok |
| queue_prioritization | YES | 422 new leads promoted newest-first; call_now page=25 |
| live_verification | NO | <urlopen error [WinError 10061] No connection could be made because the target m |
## Day Rollup (all runs)

| Run | Status | Raw | New | Dupes | Suppressed | Rejected | Needs review |
|---|---|---|---|---|---|---|---|
| `7-3300` | QUARANTINED | 2388 | 0 | 2306 | 21 | 61 | 0 |
| `1-9100` | QUARANTINED | 2388 | 0 | 2306 | 21 | 61 | 0 |
| `2-3900` | FAILED | 1415 | 422 | 894 | 65 | 34 | 0 |

**Day totals:** raw=6191, new=422, duplicates=5506, suppressed=107, rejected=156, needs_review=0