# 09 — High-Volume Data Entry Specification

Status: PROPOSED — requirements fixed by directive §14/§high-volume; UX details open
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## E1. Design goal

Crews enter LARGE numbers of receipts, bills, expenses, payments, supplier
documents, project costs daily. Correctness is never sacrificed for speed, but
every workflow must assume volume, not one-document-at-a-time.

## E2. Mandatory capabilities

| Capability | Requirement |
|---|---|
| FAST ENTRY | Keyboard-first forms: logical tab order, default dates/party/tax from context, hotkeys for save+new, recent-items quick pick |
| Sensible defaults | Today's date, user's default project/cost center, last-used account suggestions |
| Templates | Reusable document templates for recurring bills/expenses |
| DRAFTS | Autosave drafts; nothing lost on crash/logout; drafts visible to owner only until submitted |
| VALIDATION | Required-field enforcement BEFORE submit; inline errors; no silent coercion of bad input |
| DUPLICATE DETECTION | Pre-submit warning on same party+amount+date window and same attachment hash; warning ≠ block (business may legitimately have repeats), but must be explicit |
| ATTACHMENTS | Drag/drop + camera upload bound to the document; stored with metadata (doc 05) |
| BULK IMPORT | CSV import with: column mapping preview, dry-run validation report (row-level errors), import executes only after human confirms clean report; every imported row tagged with import batch id (doc 05 D4) |
| SEARCH/FILTER | Fast server-side search across party/name/code/amount/date; filters combinable; results paginated |

## E3. Document state machine (all financial documents)

```
DRAFT → SUBMITTED → APPROVED → POSTED ─┬→ REVERSED (by reversal doc)
   ↘ REJECTED (back to draft)          └→ CANCELLED (controlled)
```

- Only APPROVED documents reach the ledger, via native platform posting.
- POSTED = immutable (doc 07 C2).
- OCR pipeline feeds DRAFT creation, never skips states (doc 02 P5).

## E4. Performance targets (PROPOSAL — validate during bake-off)

- New simple expense/receipt: ≤ 30 s keyboard-only for a practiced user.
- Search results: first page < 2 s at 100k-document scale.
- Bulk import: ≥ 500 rows/batch with row-level error report.

## E5. Anti-patterns prohibited

- Modal-after-modal entry flows requiring mouse for each field.
- Posting directly from import without the dry-run gate.
- Any flow that edits a POSTED document "for convenience".

## Open items

1. Per-candidate proof of E2 rows (scenarios 28–30). [bake-off]
2. Mobile camera-capture quality on low-end Android browsers. [verify in bake-off scenario 27]
