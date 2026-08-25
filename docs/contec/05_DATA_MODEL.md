# 05 — Data Model

Status: PROPOSED — conceptual only; physical mapping depends on selected platform
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## D1. Principles

1. Canonical single store: one record per real-world entity, never per language
   (bilingual fields pattern below).
2. Every consequential value carries a trust state (doc 04 §A3).
3. Every transaction references its source document and attachment(s).
4. Posted records immutable; corrections linked, not overwritten.
5. Dimensions (project, cost center) are mandatory fields on expense/revenue
   lines where applicable — enforced at validation, not by convention.

## D2. Core entity map (conceptual)

```
Company ─┬─ FiscalYears ─── Periods
         ├─ Currencies (+ rates)
         ├─ Accounts (CoA tree) ── CostCenters
         ├─ Projects ── ProjectCostCenters
         ├─ Parties: Customers · Suppliers · Subcontractors · Employees
         ├─ Items/Warehouses/SiteStores · StockMoves
         ├─ Assets ── MaintenanceEvents
         └─ Banks/CashAccounts ── BankStatements

Documents: SalesInvoice · PurchaseBill · Payment · Receipt ·
           JournalEntry · ExpenseClaim · EmployeeAdvance · Settlement
Each Document: lines[] → {account, project?, cost_center?, tax?, qty, amount}

Cross-cutting:
Attachment(file, meta_ar, meta_en, owner_doc, uploaded_by, trust_state)
SourceDocument(type, ref, date, party, total, trust_state, attachment_ids)
AuditEvent(actor, action, object, timestamp, reason?, before?, after?)
OCRRecord(source_attachment, extracted_fields{}, confidence_map{},
          review_state, reviewed_by, reviewed_at)
Budget(project/cost_center, period, amount) ↔ Actuals(from ledger)
```

## D3. Bilingual field pattern

```
name        → canonical/reference key (code or latin slug)
name_ar     → Arabic display name      name_en → English display name
notes_ar    → Arabic notes             notes_en → English notes
```

UI locale selects which field displays; data integrity tests require both
languages' content to survive locale switches unchanged (see doc 08 tests).

## D4. Mandatory audit/provenance columns on transactions

```
posted_at, posted_by, reversed_by_of (nullable link), correction_of (nullable),
source_document_id (nullable pre-posting, REQUIRED at posting where a paper
source exists), created_from_import_id (nullable), trust_state
```

## D5. Immutability mechanics

Posted documents reject UPDATE/DELETE at the application layer AND, where the
platform permits, at the DB constraint/policy level. Corrections create new
linked documents (reversal/correction/amendment per doc 07).

## Open items

1. Map every entity to native objects of selected platform; mark BUILD-only gaps. [PENDING DECISION]
2. Retention metadata fields (legal hold, retention class). [PROPOSED]
3. Number-series design per document type (per fiscal year reset?). [PENDING DECISION]
