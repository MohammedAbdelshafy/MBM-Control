# Contec ERP — QA Release Gate

Status: GATE DEFINED — no releases exist yet; default verdict NO-GO
Owner: Terminal 3 presents evidence / Terminal 2 issues GO or NO-GO
Last updated: 2026-08-25

## Rule

Verdict is exactly `GO` or `NO-GO`. "Mostly okay" does not exist. Every line
needs linked evidence (test run output, drill record, screenshot). Missing
evidence = that line fails.

## Release checklist

| # | Criterion | Evidence required | Status |
|---|---|---|---|
| 1 | Accounting correct | accounting suite green; control-totals JSON matches after latest change/migration | PENDING |
| 2 | Permissions correct | permission suite green incl. negative tests | PENDING |
| 3 | Arabic correct | doc 08 §B4 tests green | PENDING |
| 4 | English correct | same suite, EN locale | PENDING |
| 5 | RTL correct | layout checks at both widths green | PENDING |
| 6 | No silent deletion | audit-event assertions on archive/delete paths green | PENDING |
| 7 | Backup works | scheduled backup ran; artifact verified non-empty | PENDING |
| 8 | Restore works | doc 10 Y4 drill into clean env recorded | PENDING |
| 9 | Security acceptable | SECURITY_GATE: zero critical failures | PENDING |
| 10 | No leaked credentials | secret scan clean; env template placeholders-only | PENDING |
| 11 | No critical tests failing | CI/run log attached | PENDING |
| 12 | Provenance intact | dashboard→ledger→source drill-down demo recorded | PENDING |

## Procedure

1. Terminal 3 opens a release request listing evidence links per row.
2. Terminal 2 independently re-runs spot checks (trust nothing unverified).
3. Verdict written below with date; any NO-GO lists exact failing rows.

## Verdict log

```
Release:            —
Date:               —
Verdict:            NO-GO (no release requested yet)
Failing rows:       all pending
Signed (T2):        —
```
