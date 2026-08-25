# 07 — Accounting Rules & Controls

Status: PROPOSED — invariants fixed; Egyptian specifics pending research
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## C1. Absolute invariants (any platform must satisfy)

1. **DEBITS = CREDITS** for every journal entry, enforced by the platform's
   native ledger — never by custom code writing ledger rows directly.
2. Trial balance sums to zero at any timestamp.
3. Subledgers reconcile to control accounts (AR, AP, bank, cash, inventory).
4. No transaction posts without: valid date in an OPEN period, valid account(s),
   party where applicable, currency + amount > 0 handling, and dimensions
   (project/cost center) where required by doc 05 D1.5.
5. Multi-currency: amounts stored with currency + rate at transaction date;
   revaluation rules per platform capability [PENDING RESEARCH].

## C2. Posted immutability

Posted financial records are NEVER silently edited or deleted. Corrections:

- **Reversal** — mirrored entry linked to original (default method).
- **Correction entry** — explicit adjusting JE referencing the error.
- **Controlled cancellation** — platform-native cancel flow producing the
  platform's cancellation entries.
- **Controlled amendment workflow** — only if the platform offers stateful
  amendment with full versioning; otherwise forbidden.

Normal users have NO delete permission on posted transactions. Draft documents
may be freely edited/deleted pre-submission by their owner. Any exception path
must appear in `SECURITY_GATE.md` checks before go-live.

## C3. Provenance (mirror of 04 §A2 — binding for accounting)

```
REPORT ← LEDGER ← TRANSACTION ← SOURCE DOCUMENT ← ATTACHMENT/RECEIPT/INVOICE
```

A posted document should reference its source document; the source references
its attachment(s). Reports must be reconstructable from ledger alone; AI prose
never substitutes for ledger values.

## C4. Tax handling

Every tax-bearing line shows its tax code explicitly; tax amounts are computed
by the platform, not hand-keyed, wherever the platform supports it.
Egyptian specifics — VAT rates/categories by construction-service type,
withholding on subcontractors, retention — are **PENDING RESEARCH**
(Terminal 1, primary sources: ETA material). ETA e-invoicing integration is a
SEPARATE validated phase after V1 (mission brief FACT).

## C5. Period close

Open/close period control per fiscal period; closed periods reject new or
amended postings except via controlled reopening audited to an administrator.
Mechanism = platform-native [verify per candidate].

## C6. AI/OCR boundary (accounting side)

OCR/AI output enters as NEEDS_REVIEW/UNVERIFIED draft data ONLY. Posting happens
exclusively through human-approved native workflows. No automated posting rule
may exist that skips review when confidence is low, and no "auto-post" toggle
exists anywhere in Contec configuration.

## Open items

1. Egyptian VAT/WHT/retention rulebook with citations. [PENDING RESEARCH]
2. Depreciation policy per asset class. [PENDING DECISION]
3. Advance/settlement GL pattern (employee control account). [PROPOSED:
   employee receivable control account; settle via expense allocation]
4. Bank reconciliation cadence. [PROPOSED: monthly minimum]
