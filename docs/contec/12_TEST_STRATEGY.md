# 12 — Test Strategy

Status: PROPOSED — structure fixed; suites materialize with each implementation milestone
Owner: Terminal 2 (test strategy) / Terminal 3 (authoring later)
Last updated: 2026-08-25

## T1. Principles

1. Every milestone ships tests WITH the feature; a milestone without its tests
   is not done (Definition of Done, mission brief).
2. Accounting invariants are tested continuously, not once.
3. Tests must be reproducible from the repo (seeded fixtures), hermetic where
   possible (no external network for unit/integration).
4. The bake-off harness (doc: PLATFORM_BAKEOFF) doubles as the seed regression
   suite after platform selection — write once, reuse.

## T2. Suite map

| Suite | Scope | Gate |
|---|---|---|
| Unit | custom-app logic (trust states, provenance resolution, import validators) | every commit |
| Integration | document flows through platform API: bill→payment, invoice→receipt, advance→settlement | per milestone |
| Accounting | JE balance; trial-balance zero-sum; reversal correctness; duplicate-posting prevention; partial payments; period-close rejection of closed-period posting | per milestone + nightly |
| Permission | each role CAN do its domain / CANNOT do others; creator≠approver enforcement; posted-record immutability per role | per milestone |
| Arabic/English | doc 08 §B4 six acceptance tests | per milestone touching UX/data |
| RTL/LTR | layout mirror checks at 360px + desktop | UI milestones |
| Mobile | core entry + approval flows on mobile viewport | UI milestones |
| Import | dry-run error reporting; batch tagging; no partial silent imports | import feature |
| OCR pipeline | confidence thresholds route to NEEDS_REVIEW; no auto-post path exists (assert absence) | OCR feature |
| Backup/Restore | full Y4 drill on staging | pre-release + quarterly |
| Security | auth required everywhere; RBAC negative tests; attachment access control; secrets scan clean | pre-release |
| Performance sanity | 8+ concurrent users on core flows; search < 2 s at scale fixture | pre-go-live |

## T3. Fixtures & seed data (bake-off dataset, reused post-selection)

- Company "Contec Test" + EGP base + USD secondary
- 3 projects × 2 cost centers each; 10 customers, 10 suppliers, 5 employees
- 30-day transaction history covering every doc type incl. Arabic-named entities
- Known control totals exported to a JSON file that accounting tests assert
  against after any migration/restore.

## T4. Definition of Done (per feature)

CODE + TESTS + SECURITY check + DOCS update + DEPLOYMENT note (compose/env
impact) — all five, else the milestone report lists it as NOT done.

## T5. Failure handling

Failing critical tests block release (QA gate doc). Flaky tests are quarantined
with an issue, never deleted silently. No test is marked passing without
evidence in CI or recorded run output.
