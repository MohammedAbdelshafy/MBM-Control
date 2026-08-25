# 01 — Business Requirements

Status: SKELETON v0.1 — partially sourced, open items pending research
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## Evidence key

FACT · PROPOSAL · PENDING DECISION · VERIFIED · UNVERIFIED

## 1. Company context

| Item | Value | Class |
|---|---|---|
| Industry | Construction (Egyptian company) | FACT (mission brief) |
| Users at go-live | Owner/Director + ≥8 additional role-based users (~10 total) | FACT (mission brief) |
| Software licensing cost | Zero (open-source foundation mandatory) | FACT (mission brief) |
| Languages | Arabic + English, both first-class | FACT (mission brief) |
| Historical migration | NOT in scope; opening balances only | FACT (mission brief) |
| Company legal name | — | PENDING RESEARCH |
| Legal form / registrations | — | PENDING RESEARCH |
| Fiscal year start | — | PENDING DECISION |
| Base currency assumption | EGP | PROPOSAL — NOT APPROVED |
| Branches/sites count | — | PENDING RESEARCH |

## 2. V1 functional scope (from mission brief)

FACT — verbatim scope of `docs/CONTEC_ERP_AGENT_MISSION.md`:

- Accounting / double-entry / GL / AR / AP
- Customers and suppliers
- Customer invoices and supplier bills
- Payments, cash and bank accounts
- Projects and project profitability
- Cost centers / analytic accounting
- Budgets and actual-vs-budget
- Employee advances and expenses
- Procurement and supplier workflows
- Inventory and site stores
- Assets, equipment and maintenance
- Subcontractors
- Simple contracts
- Management dashboards
- ≥8 additional role-based users besides owner/developer
- Arabic + English responsive web UI
- Audit trail and approval controls
- Opening balances (no historical transaction migration)
- Egyptian tax configuration; ETA e-invoicing integration treated as a separate validated phase

## 3. Explicit V1 exclusions

FACT (mission brief): BOQ, quantity measurement engine, BOQ-based progress
certificates, full custom ERP rebuild.

## 4. Operational requirements (derived)

PROPOSAL — derived from directives; not business-signed:

| Requirement | Rationale |
|---|---|
| High-volume document entry (receipts, bills, expenses, payments) | Site crews enter many small documents daily |
| Receipt photo/PDF pipeline with OCR + human review | Paper receipts from sites are expected primary input |
| Mobile-browser access for site roles | Field usage on phones/tablets |
| Audit trail on every financial action | Trust + Egyptian bookkeeping practice |
| Backup/restore proven before go-live | Data ownership and recoverability |

## 5. Open questions blocking precision (owner: Terminal 1)

All classes below: PENDING RESEARCH unless answered by the business.

1. Company legal name(s), tax registration number, ETA portal status.
2. Actual fiscal year calendar and current opening-balance snapshot date.
3. Expected document volumes/day per type (drives performance targets).
4. Number of concurrent users peak (validates "8+" sizing).
5. Bank list and statement formats available (bank reconciliation design).
6. VAT treatment specifics used by the company (construction services,
   subcontractor withholding, retention receivables/payables).
7. Payroll in/out of scope for V1? Mission lists employee advances/expenses but
   is silent on payroll — assumed OUT of V1 (PROPOSAL).
8. Fixed-asset register scale (count of assets) and depreciation policy.
9. Existing hardware/server availability and internet reliability at office/site.
10. Retention/legal requirements for document storage duration (Egypt).

## 6. Acceptance for this document

This section becomes VERIFIED when Terminal 1 answers §5 with sources and the
business signs off. Until then the doc is a controlled skeleton.
