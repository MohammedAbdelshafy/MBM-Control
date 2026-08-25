# 07 — Accounting Rules

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-005, D-014..D-017
Invariant #1 (absolute): every POSTED transaction satisfies DEBITS == CREDITS.
Enforced by the ERPNext GL engine; never bypassed by custom code.

## 1. Chart of Accounts strategy

Base: ERPNext "Standard" template, then restructured into Egyptian-practice
numbered hierarchy via fixtures (import once, version-controlled CSV):

```
1000 ASSETS
 1100 Current Assets
  1110 Cash & Banks          → one leaf account per drawer/bank (P5)
  1120 Employee Advances      → control; per-employee child accounts
  1130 Receivables            → Debtors control + per-customer children
  1140 Retention Assets       (subcontractor/customer retention)
  1150 VAT Input (recoverable)
 1200 Inventory               → per warehouse group
1300 FIXED ASSETS             (register-level in V1)
2000 LIABILITIES
 2100 Payables               → Creditors control + per-supplier children
 2200 Employee Deductions / Payroll payable
 2300 Advance from Customers
 2400 Retention Payable
 2500 VAT Output (payable)
3000 EQUITY                  (capital, draws)
4000 PROJECT REVENUE         → per-project children (auto-created with Project)
5000 DIRECT COSTS            → materials / subcontract / equipment / site labor
6000 INDIRECT & OVERHEAD     → HQ cost center only
7000 FINANCE COSTS
```
Rules:
- Party ledgers use control+children pattern (per-party subledgers reconciling
  to control).
- Account creation/renaming = CHIEF_ACCOUNTANT + admin fixture change; never by
  entry users.
- Frozen accounts after period close (Accounts Settings `acc_frozen_upto`).

## 2. Cost Center hierarchy

```
CONTEC (root)
 ├── HQ-OVERHEAD
 └── PRJ-{code}            ← auto-created when Project is created (hook)
      ├── PRJ-{code}-MAT   materials
      ├── PRJ-{code}-SUB   subcontract
      ├── PRJ-{code}-EQP   equipment
      ├── PRJ-{code}-LAB   site labor
      └── PRJ-{code}-OBS   other site costs
```
Every revenue/cost document MUST resolve to a leaf cost center. Defaulting:
project → MAT default for stock issues, OBS otherwise. HQ-OVERHEAD is the only
legal target when project is empty and requires a reason code field (custom).

## 3. Project accounting

Project ↔ Cost Center ↔ Warehouse triad is created atomically by hook on
Project insert (`PRJ-{abbr}`, `WH-{abbr}`). Profitability = GL-by-cost-center +
stock consumption valuation; committed cost = open POs by cost center (custom
report V1.1). Revenue side: Sales Invoices tagged to project.

## 4. Tax handling (Egyptian practice, fixtures not core edits)

| Mechanism | Template | Effect |
|---|---|---|
| VAT output | `EG VAT Output 14%` / `15%` (rate set at go-live per prevailing law) | credit VAT Output account on Sales Invoice submit |
| VAT input | same rates purchase-side | debit VAT Input on Purchase Invoice |
| WHT services/subcontractors | `EG WHT Services 3%`, `EG WHT Professional 5%`, `EG WHT Supplies 1%` (verify schedule at go-live) | deducted from supplier payment; debited to prepaid/withheld asset; remittance JE monthly |
| Exempt/zero-rated | template with 0% + reason note field | audit trail |

DISCLAIMER: rates/schedules above are placeholders pending Chief Accountant
confirmation against current Egyptian tax law at go-live; templates make rate
changes a config edit, not a migration.

## 5. Standard posting patterns (reference table)

| Event | Debit | Credit |
|---|---|---|
| Supplier bill (materials) | Inventory/Cost (per item) + VAT Input | Creditors control |
| Supplier payment | Creditors control | Bank/Cash (+WHT asset if withheld) |
| Customer invoice | Debtors control | Project Revenue + VAT Output |
| Customer receipt | Bank/Cash | Debtors control |
| Petty cash voucher | Expense account (cost center leaf) | Drawer cash account |
| Advance to employee | Employee Advances/{emp} | Bank/Cash |
| Advance settlement via claim | Expense account | Employee Advances/{emp} |
| Unused advance returned | Bank/Cash | Employee Advances/{emp} |
| Stock issue to project | Project MAT cost center expense | Inventory account |
| Stock count variance | Inventory adj. expense (or reverse) | Inventory account |
| Period close | Revenue accounts | P&L summary (and reverse for costs) |

## 6. Payments & allocation

Partial payments allowed (Payment Entry allocation). Overpayment blocked >
tolerance 1 EGP without Chief override reason. Payment modes map 1:1 to
bank/drawer leaf accounts; bank reconciliation monthly before close (P8).

## 7. Authorization thresholds (D-014)

| Action | Limit | Approver |
|---|---|---|
| Payment Entry direct submit | ≤ EGP 50,000 | ACCOUNTANT |
| Payment Entry submit | > EGP 50,000 | GM or CHIEF (WF-4b) |
| Journal Entry any amount | all | CHIEF_ACCOUNTANT only |
| PO approval | ≤ EGP 200,000 CHIEF or GM; > requires OWNER countersign workflow state | |
| Cancel submitted financial doc | any | CHIEF (GM below threshold) |
Thresholds are fixtures (single place), adjustable by owner decision recorded
in DECISION_LOG.md.

## 8. Opening balances & go-live cutover

One cutover date. Sequence: (1) CoA + cost centers live; (2) opening JE for
GL balances signed by Chief; (3) party balances via Opening Invoice Creation
Tool; (4) stock quantities via Stock Reconciliation; (5) trial balance printed,
compared to pre-cutover manual TB, variance=0 required; (6) freeze prior periods.

## 9. Period closing

Monthly checklist (02 §P8). After Process Period Closing Voucher + frozen-date
set, NO posting into closed month is possible without Chief unfreeze action,
which itself is logged. Year-end repeats process + equity transfer JE (Chief).

## 10. AI/API posting prohibition (R8)

- Workflow states require role transitions that no API token possesses (06 §5 I4).
- Server-side guard hook: reject doc submission where `owner` session is an API
  key for doctypes in {Journal Entry, Payment Entry, Sales Invoice, Purchase
  Invoice, Expense Claim submit-to-post, Stock Reconciliation} unless
  `contec.allow_system_post` flag explicitly enabled per-environment (default OFF).
- AI outputs write ONLY to suggestion fields on drafts (D-011).
