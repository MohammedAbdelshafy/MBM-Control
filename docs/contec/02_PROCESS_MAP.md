# 02 — Process Map (Contec V1)

Status: APPROVED (Terminal 1) · Date: 2026-08-25
Platform mapping assumes ERPNext v16 (see 03_ERP_PLATFORM_DECISION.md).
ERPNext doctype names are in `[brackets]`.

## P0. Master data lifecycle

```
Customer/Supplier/Item/Employee created (DRAFT)
  → verified by Accountant or Chief Accountant
  → ACTIVE (usable in transactions; bilingual name_en/name_ar required)
  → never deleted once referenced; deactivate instead [disabled flag]
```

## P1. Procurement-to-pay (supplier cycle)

```
Procurement Officer            Accountant / Chief Accountant          Payment
────────────────────           ────────────────────────────           ───────
Purchase Requisition (optional, site request)
  → Purchase Order [Purchase Order]  ──(SUBMIT = human approval)──┐
       │  project + cost center mandatory                          │
       ▼                                                           │
   Goods receipt at site store [Purchase Receipt] → Stock Ledger   │
       ▼                                                           ▼
   Supplier bill arrives (paper/PDF/photo)                         │
       → [Purchase Invoice] entered with: supplier, bill no+date,  │
         items/expenses, VAT template, WHT template,               │
         project + cost center                                     │
       → DUPLICATE CHECK (supplier+bill_no hard unique; fuzzy warn)│
       → SUBMIT (Accountant+) → AP ledger + GL posted              │
       ▼                                                           ▼
   Payment Entry [Payment Entry] (Pay) allocates against invoice ──┘
       SUBMIT (Accountant+, amount thresholds per 07 §7) → GL + bank/cash ledger
```

Controls: PO approval gate before ordering; 3-way feel (PO ↔ receipt ↔ bill)
reported but not hard-blocked in V1; WHT auto-deducted on submit per tax template.

## P2. Quote-to-cash (customer cycle)

```
Contract signed (Contec Contract register [custom: Contec Contract])
  → Customer invoice / progress billing [Sales Invoice]
      (project + cost center mandatory; VAT per template)
  → SUBMIT (Accountant+) → AR + GL
  → Receipt [Payment Entry] (Receive) → allocate → GL
  → AR aging report weekly to GM/Owner
```

Retention/advance from customer booked as liability via Journal Entry
(Journal Entry is CHIEF_ACCOUNTANT-only).

## P3. Expense & employee-advance cycle

```
Site Engineer / any employee
  → paper voucher + photo
  → phone entry:
      A) Cash expense → [custom: Contec Expense Voucher] draft
         (amount, paid_to, mode=petty_cash/drawer, photo attachment,
          project + cost center) 
      B) Expense claim → [Expense Claim] (hrms) with attachments
      C) Advance request → [Employee Advance] (hrms) draft
  → review & classify (Accountant): account, cost center, VAT if any
  → SUBMIT → GL posting path:
      cash drawer credit / advance asset debit (D-015)
  → Advance settlement: [Expense Claim] linked to advance OR
    [Journal Entry] return of unused cash — both CHIEF_ACCOUNTANT approved
```

## P4. Inventory (site stores)

```
[Material Request] (Site Engineer/PM, draft)
  → [Purchase Order] (P1) for buys
  → [Stock Entry] Material Transfer: main warehouse → site warehouse
  → [Stock Entry] Issue/Receive/Reconcile by Storekeeper (SUBMIT allowed)
Every Stock Entry carries project + cost center when consuming materials.
Stock consumption valuation posts to project cost accounts (perpetual inventory ON).
Monthly store count → Stock Reconciliation → variance Journal Entry (Chief only).
```

## P5. Petty cash / drawers

Each physical cash drawer = one ERPNext "Cash" account under a Drawer parent.
```
Imprest top-up:  JE (bank → drawer)        [Chief Accountant]
Voucher spend:   Contec Expense Voucher → JE-like GL line (drawer credit)
Count surplus/shortage: JE (cash over/under account) [Chief only]
```

## P6. Subcontractors

```
Subcontractor = Supplier (type=Subcontractor group)
Subcontract agreement → [custom: Contec Contract] record
Progress bill → [Purchase Invoice] with subcontract WHT template
Retention held → [custom: retention via Journal Entry] liability line (Chief only)
Payment → [Payment Entry] net of WHT + retention
```

## P7. Receipt/document digitization pipeline (OCR-ready)

```
PHOTO/PDF (phone camera or file)
  → attached to draft document (mandatory above EGP threshold, D-010)
  → [custom: Contec Document] stores file + source metadata
  → (Phase 2) OCR/extraction job fills suggested fields + confidence
  → HUMAN REVIEW screen (never auto-posted, D-011)
  → accounting classification (account/VAT/project/cost center)
  → SUBMIT → LEDGER
```

## P8. Period close (monthly)

```
1. All drafts of the month either submitted or cancelled
2. Bank/cash reconciliations completed
3. Stock reconciliations posted
4. Depreciation posted (if assets active)
5. Period Closing Voucher [Process Period Closing Voucher] (CHIEF_ACCOUNTANT)
6. Accounts frozen before close date (Accounts Settings frozen threshold)
```

## P9. Reporting cadence

| Report | Audience | Frequency |
|---|---|---|
| Project Profitability (revenue vs actual cost vs committed) | Owner, GM, PM | Live |
| Cash position (drawers + banks) | Owner, GM, Chief | Daily |
| AR aging / AP aging | GM, Chief | Weekly |
| Budget vs actual per cost center | GM, PM | Monthly |
| Advances outstanding | Chief, HR | Biweekly |
| P&L / Balance Sheet / Trial Balance | Owner, Chief | Monthly |

## P10. Approval authority summary

Full matrix: 06_USER_ROLES.md. Principle: creators cannot approve their own
documents; SUBMIT rights on financial doctypes are limited to ACCOUNTANT and
above; Journals/Payment Entries above threshold require CHIEF_ACCOUNTANT (07 §7).
