# Daily Lead Ingestion Report — daily-ingest-20260824T123907-3300

- **Status:** `QUARANTINED` (dry_run)
- **Source:** `npi_verified_callsheet.json@2026-08-23T11:55:59.239638+00:00`
- **Started:** 2026-08-24T12:39:07.273563+00:00  |  **Completed:** 2026-08-24T12:39:12.615189+00:00

| Metric | Count |
|---|---|
| Raw | 2388 |
| Accepted | 0 |
| New | 0 |
| Duplicates | 2306 |
| Suppressed | 21 |
| Rejected | 61 |
| Needs review | 0 |

- **Canonical:** before=4484 after=4484 revision=36->36
- **Dataset hash:** `b353215d8652e0b7…`
- **Script coverage:** 100.0%  |  **Segment coverage:** 100.0%
- **Live verified:** NO

## Stage Pipeline

| Stage | Completed | Detail |
|---|---|---|
| source_fetch | YES | 2388 rows from npi_verified_callsheet.json@2026-08-23T11:55:59.239638+00:00 |
| raw_ingest | YES | 2385 structured candidates (3 malformed dropped) |
| phone_identity_validation | YES | US phone + identity gate applied to every candidate |
| provenance_validation | YES | LeadProvenanceGate applied to every candidate |
| synthetic_check | YES | strong synthetic fingerprint veto applied |
| dedupe | YES | 2306 duplicates (2190 enriched via history-preserving merge) |
| suppression_dnc_check | YES | 21 suppressed/DNC (suppression index size 102) |
| classification | YES | 0 NEEDS_REVIEW; segments=[] |
| script_assignment | YES | coverage 100.0% (canonical script engine) |
| canonical_write | YES | dry-run: no write performed |
| revision_audit | YES | dry-run: no revision bump |
| queue_prioritization | YES | planned newest-first order (dry-run) |
| live_verification | YES | dry-run: live release check deferred until --apply |
## Day Rollup (all runs)

| Run | Status | Raw | New | Dupes | Suppressed | Rejected | Needs review |
|---|---|---|---|---|---|---|---|
| `1-9100` | QUARANTINED | 2388 | 0 | 2306 | 21 | 61 | 0 |
| `7-3300` | QUARANTINED | 2388 | 0 | 2306 | 21 | 61 | 0 |

**Day totals:** raw=4776, new=0, duplicates=4612, suppressed=42, rejected=122, needs_review=0