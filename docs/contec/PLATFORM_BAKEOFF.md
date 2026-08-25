# Contec ERP — Platform Bake-Off

Status: METHODOLOGY v1.0 (ready to execute) — RESULTS EMPTY, NO WINNER
Owner: Terminal 1 executes / Terminal 2 scores-verifies / Operator approves winner
Last updated: 2026-08-25

## 1. Purpose

Select the ERP foundation for Contec on EVIDENCE, not popularity or marketing.
This document defines a repeatable, identical test every candidate must pass.
No candidate may be declared winner without a completed scorecard here plus the
decision record in `03_ERP_PLATFORM_DECISION.md`.

## 2. Candidates

ERPNext · Odoo Community · Axelor Open Suite · Dolibarr · Tryton · Open Mercato
· iDempiere · Flectra · any serious addition discovered in research.
Desk-research gate first: license + community health + Arabic support evidence
+ official Docker story must exist BEFORE spending hands-on effort. Top ~3 by
documented desk research proceed to full hands-on.

## 3. Identical environment rule

Every candidate runs from its OFFICIAL Docker images (or documented compose)
with identical host resources; identical seed dataset (doc 12 T3); same browser
set (desktop Chrome + Android mobile viewport). Deviations are recorded as
notes and cannot be silently dropped.

## 4. Scenario matrix (34)

| # | Scenario | Pass criteria (evidence required) |
|---|---|---|
| 1 | Create company | Company exists; base currency EGP settable |
| 2 | Chart of accounts | Import/create CoA tree ≥ 3 levels |
| 3 | Create project | Project with code + AR/EN name fields achievable (native or extension) |
| 4 | Create cost center | Cost center attachable to transactions |
| 5 | Customer | incl. Arabic-only name record |
| 6 | Supplier | incl. Arabic-only name record |
| 7 | Supplier bill | Posts DR expense/CR AP; dimensions captured |
| 8 | Supplier payment | AP cleared/partial; bank entry correct |
| 9 | Customer invoice | DR AR / CR revenue + tax line explicit |
| 10 | Customer receipt | Partial allocation; outstanding correct after |
| 11 | Employee advance | Employee receivable pattern native or clean extension |
| 12 | Advance settlement | Expense offset + residual cash return balances to zero |
| 13 | Purchase material | PO→receipt linkage or equivalent control |
| 14 | Receive material | Stock + GR/IR-style accounting consistent |
| 15 | Issue material to project | Stock credit → project cost debit with dimension |
| 16 | Project expense | Lands in project profitability |
| 17 | Project profitability | Revenue − costs per project, drillable to ledger |
| 18 | P&L | Standard report correct vs seeded control totals |
| 19 | Balance sheet | Balances; matches control totals |
| 20 | AR aging | Buckets correct incl. partial payments |
| 21 | AP aging | Same |
| 22 | 8+ users | Create 10 users across doc 06 archetypes |
| 23 | Role permissions | Negative tests pass (role X cannot do Y); creator≠approver enforced; server-side checks verified (API call without UI) |
| 24 | Arabic UI | Full navigation usable in Arabic |
| 25 | English UI | Full navigation usable in English |
| 26 | RTL | Correct mirroring; no clipping at 360px & desktop |
| 27 | Mobile | Complete bill+receipt cycle on phone viewport |
| 28 | CSV import | Dry-run error report then clean import of ≥100 rows; rows tagged |
| 29 | Attachment upload | Attach to document; permission-controlled retrieval |
| 30 | Duplicate detection | Warning surfaces same party+amount+date re-entry |
| 31 | Backup | Documented scriptable backup executes successfully |
| 32 | Restore | Restore drill (doc 10 Y4 abbreviated) passes into CLEAN env |
| 33 | API | Read AND write via API with scoped token; write respects approval workflow |
| 34 | AI read-only retrieval | Scoped read-only token retrieves business data; no write path available to that token |

## 5. Scoring rubric (per scenario per candidate)

```
0 = unavailable
1 = custom build required
2 = difficult/brittle extension possible
3 = supported with configuration
4 = native and mature
5 = native, mature, well tested (community-documented behavior)
```

Weights (sum-normalized): accounting scenarios 7–12,18–21 ×3;
permissions 22–23 ×2; bilingual 24–26 ×2; import 28 ×2;
backup/restore 31–32 ×2; all others ×1.

## 6. Disqualifiers (any ⇒ candidate eliminated regardless of score)

- Not true double-entry, or allows unbalanced posting.
- Posted records editable/deletable without trace (violates D-008).
- No viable extension mechanism without core fork.
- License terms incompatible with zero-cost commercial internal use
  [verify current license text — UNVERIFIED until cited].
- No credible path to Arabic/RTL.

## 7. Evidence rules

Each scored cell needs: screenshot OR CLI output OR DB query result + one-line
note. Claims without evidence are recorded as UNVERIFIED and score 0 until
proven. Marketing material is never evidence.

## 8. Result scorecards

> To be filled during execution — one table per candidate. Empty now BY DESIGN.

| Candidate | Weighted score | Disqualifiers hit | Evidence pack link | Verifier (OX2) |
|---|---|---|---|---|
| ERPNext | NOT RUN | — | — | — |
| Odoo Community | NOT RUN | — | — | — |
| Axelor | NOT RUN | — | — | — |
| Dolibarr | NOT RUN | — | — | — |
| Tryton | NOT RUN | — | — | — |
| Open Mercato | NOT RUN | — | — | — |
| iDempiere | NOT RUN | — | — | — |
| Flectra | NOT RUN | — | — | — |

## 9. Winner declaration template (for later)

Winner = highest weighted score among candidates with zero disqualifiers,
confirmed by OX2 verification and operator approval recorded in DECISION_LOG.
Ties/near-ties resolved by upgrade-safety + community-health review, documented.
