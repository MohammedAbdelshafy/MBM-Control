# 05 — Data Model

Status: APPROVED (Terminal 1) · Date: 2026-08-25
One canonical dataset. Language is presentation, never duplication (D-003).

## 1. Canonical entities → ERPNext doctype mapping

| Contec entity | Doctype (module) | Notes |
|---|---|---|
| Company | Company | single company "Contec", EGP |
| Fiscal calendar | Fiscal Year | Gregorian, Jan–Dec default |
| Chart of accounts | Account | tree; strategy in 07 §1 |
| Project | Project | one per construction site/contract execution |
| Cost center | Cost Center | hierarchy mirrors 07 §2 |
| Customer | Customer | groups: Government / Private / Developer |
| Supplier | Supplier | groups: Material / Equipment / Subcontractor / Services / Other |
| Item (materials) | Item | stock items + service items; bilingual names |
| Warehouses | Warehouse | `Main Store` + one per site: `WH-{PROJECT}` |
| Contract register | **custom `Contec Contract`** | non-financial metadata linking Project↔Customer↔value↔dates |
| Purchase order | Purchase Order | project+cost_center mandatory |
| Goods receipt | Purchase Receipt | against PO, to site warehouse |
| Supplier bill | Purchase Invoice | duplicate guard (09 §6) |
| Customer invoice | Sales Invoice | VAT template mandatory |
| Payment in/out | Payment Entry | allocation to invoices; multi-mode |
| Journal entry | Journal Entry | CHIEF_ACCOUNTANT only (06) |
| Petty cash spend | **custom `Contec Expense Voucher`** | drawer credit path 02 P5 |
| Employee advance | Employee Advance (hrms) | verified present v16 |
| Expense claim | Expense Claim (hrms) | linked advance settlement supported |
| Stock movement | Stock Entry / Stock Reconciliation | perpetual inventory ON |
| Digitized source doc | **custom `Contec Document`** | file + extraction JSON + review state |
| Tax behavior | Sales/Purchase Taxes and Charges Templates | EG VAT + WHT fixtures (D-005) |
| Budgets | Budget vs Cost Center | optional V1.1 |

## 2. Bilingual field convention (all master data)

```
customer_name      ← canonical unique key (either script)
customer_name_en   ← English rendering (nullable but REQUIRED for reporting)
customer_name_ar   ← Arabic rendering (nullable but REQUIRED for Arabic print)
search_norm        ← auto-generated normalization of all name parts (08 §7)
```
Rule: at least ONE of en/ar must be filled at save; reports fall back
canonical → current-language → other language. Transaction documents store
references to masters plus their own `title` (bilingual via masters), never
free-text duplicates of master names.

## 3. Mandatory attribution fields on every financial transaction

`company`, `posting_date`, `project` (or explicit `is_hq_overhead`),
`cost_center` (defaults from project; overridable downward only),
`currency=EGP` (multi-currency fields exist but V1 posts EGP only — D-016),
taxes via template reference (never ad-hoc rates).

## 4. Document numbering (V1)

ERPNext naming series, configured as:

| Doc | Series |
|---|---|
| Purchase Invoice | ACC-PINV-.YYYY.-.##### |
| Sales Invoice | ACC-SINV-.YYYY.-.##### |
| Payment Entry | ACC-PAY-.YYYY.-.##### |
| Journal Entry | ACC-JV-.YYYY.-.##### |
| Expense Voucher | CNT-EV-.YYYY.-.#### |
| Contec Contract | CNT-CON-.YYYY.-.### |

Supplier bill number is a DATA field (`bill_no`) with uniqueness rule — never
the internal series (external truth preserved).

## 5. Attachment & audit columns (platform-provided)

Every document automatically carries: `owner`, `creation`, `modified_by`,
`modified`, `docstatus` (0 draft / 1 submitted / 2 cancelled), plus Version
history and Access Log rows. Attachments stored under site private files;
financial docs attach into PRIVATE zone only (11 §6). Custom `Contec Document`
adds: `source_type` (photo/pdf/scan), `sha256` (dedupe), `extraction_json`,
`review_state`, `reviewed_by`.

## 6. Immutability & reversal model

Submitted = immutable row set feeding GL. Corrections:
- before submit: edit freely by owner role;
- after submit: CANCEL (creates docstatus=2) then AMEND → new draft lineage.
No UPDATE-in-place of posted values is permitted by platform design; any code
attempting `db.set_value` on submitted financial docs fails review (12 T-SEC).

## 7. Opening balances (R13)

Opening balances enter as dated opening entries: Party balances via
Opening Invoice Creation Tool; account balances via one Opening Journal Entry
per 07 §8; stock quantities via opening Stock Reconciliation. No history import.

## 8. Volume & indexing plan

Hot query paths get composite indexes via property-setter/index fixtures:
PurchaseInvoice(`supplier,bill_no,docstatus`), PaymentEntry(`party,posting_date`),
StockLedgerEntry(`warehouse,posting_date`), GL Entry(`cost_center,project,
posting_date`). Fuzzy-duplicate candidate query uses the indexed
`(supplier, posting_date window, grand_total)` prefilter before scoring (09 §6).
