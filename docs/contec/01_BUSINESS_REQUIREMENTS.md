# 01 — Contec Business Requirements

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Owner: Chief ERP Architect
Supersedes nothing. Parent mission: `docs/CONTEC_ERP_AGENT_MISSION.md`.

## 1. Company profile

| Item | Value |
|---|---|
| Company | Contec — Egyptian construction & contracting |
| Legal currency | EGP (Egyptian Pound) |
| Language of operation | Arabic (spoken/written) + English (business/technical) |
| Sites | Head office + multiple concurrent construction projects/site stores |
| Regulatory context | Egyptian VAT (14–15% regime), withholding tax on services/subcontractors, ETA e-invoicing mandate (phase-gated, see 13_ROADMAP) |

## 2. Hard requirements (non-negotiable)

R1. Production-grade ERP, NOT a demo, NOT a toy CRM.
R2. Roles supported: OWNER, GENERAL_MANAGER, CHIEF_ACCOUNTANT, ACCOUNTANT,
    PROJECT_MANAGER, SITE_ENGINEER, PROCUREMENT_OFFICER, STOREKEEPER.
R3. Minimum 8 named additional users besides owner/developer, concurrently.
R4. Bilingual AR+EN UI, RTL+LTR, single canonical dataset (no second database).
R5. Usable from Desktop, Tablet, Android phone, iPhone (responsive web; native apps NOT required).
R6. High-volume data entry is FIRST-CLASS: hundreds/thousands of receipts,
    supplier invoices, customer invoices, payments, expenses, employee advances,
    settlements, project expenses, procurement records, inventory movements.
R7. Double-entry integrity always: every posted transaction has DEBITS == CREDITS.
R8. Financial posting requires human authorization. No AI agent may post silently.
R9. Use the selected ERP's existing accounting engine. NO custom accounting engine.
R10. NO BOQ in V1. No quantity-measurement engine, no BOQ progress certificates.
R11. Zero software licensing cost (open-source foundations only).
R12. Self-hosted, data owned by Contec, automated backups with proven restore.
R13. Opening balances migration only; NO historical transaction migration in V1.

## 3. Document volumes (design targets)

| Document class | Volume/month | Entered by | Device |
|---|---|---|---|
| Petty-cash receipts / site vouchers | 500–2,000 | Site Engineer, Storekeeper, Accountant | Phone, desktop |
| Supplier bills | 100–500 | Accountant, Procurement | Desktop, tablet |
| Customer invoices / progress billing (non-BOQ) | 20–80 | Accountant | Desktop |
| Payments (cash/bank) | 200–800 | Accountant | Desktop |
| Employee advances + settlements | 30–150 | Accountant, PM | Desktop, phone |
| Expense claims | 50–300 | Any salaried role | Phone-first |
| Purchase orders | 50–200 | Procurement | Desktop |
| Inventory receipts/issues/transfers | 300–1,500 | Storekeeper | Tablet/phone-first |
| Subcontractor invoices/payments | 10–50 | Accountant | Desktop |

Design consequence: mobile-first entry screens for receipts/expenses/stock;
desktop-first for invoices/journals/reports. See 09_DATA_ENTRY_SPEC.md.

## 4. Business object hierarchy

```
COMPANY
  └── PROJECT            (each construction contract site)
        └── CONTRACT     (customer agreement driving revenue)
              └── COST CENTER(s)   (cost breakdown inside the project)
                    ├── REVENUE         (customer invoices, receipts)
                    ├── PURCHASING      (POs, supplier bills)
                    ├── EXPENSES        (cash expenses, expense claims)
                    ├── INVENTORY       (site store receipts/issues)
                    ├── SUBCONTRACTORS  (subcontract bills, WHT, payments)
                    ├── EMPLOYEE ADVANCES (+ settlements)
                    └── PAYMENTS        (in/out, cash/bank)
                          └── PROJECT PROFITABILITY (report, live)
```

Rules:
- Every cost/revenue document MUST carry Project + Cost Center attribution
  (enforced by mandatory fields and Accounting Dimensions).
- A document without a cost objective is booked to HQ overhead cost center.
- BOQ is excluded from V1 by decision D-006.

## 5. Users and devices

| Role | Count (initial) | Primary device | Entry intensity |
|---|---|---|---|
| Owner | 1 | Phone, desktop | Read/approve |
| General Manager | 1 | Desktop, phone | Read/approve |
| Chief Accountant | 1 | Desktop | Heavy review/post |
| Accountant | 2–3 | Desktop | Heavy entry |
| Project Manager | 1–2 | Tablet, phone | Medium entry |
| Site Engineer | 2–4 | Phone | High entry (receipts/photos) |
| Procurement Officer | 1–2 | Desktop | Medium entry |
| Storekeeper | 2–4 | Tablet/phone | High entry (stock) |

Connectivity assumption: sites have intermittent 4G; system MUST tolerate slow
links (lightweight pages, resumable uploads) but OFFLINE mode is explicitly OUT
of V1 scope (documented honestly in 09_DATA_ENTRY_SPEC §9).

## 6. Success criteria

S1. 8+ users work simultaneously with least-privilege permissions (verified negative tests).
S2. One month of real operations entered (≥300 documents) with zero unbalanced postings.
S3. Project profitability report reconciles to GL within defined tolerance for every project.
S4. Arabic-speaking site staff can enter a receipt with photo attachment in ≤60 seconds on a phone.
S5. Nightly backup runs; restore into clean environment succeeded before go-live.
S6. Duplicate supplier bill number cannot be posted twice (hard block).
S7. Every financial document shows who created/approved/posted it (audit trail).

## 7. Explicit exclusions (V1)

BOQ/quantity takeoff · payroll engine (advances/expenses only) · fixed-asset
depreciation schedules beyond simple asset register · manufacturing · e-commerce ·
offline-first mobile apps · historical transaction migration · automatic ETA
submission (separate validated phase, D-012).

## 8. Traceability

Each requirement maps to specs: R1→12, R2/R3→06, R4/R5→08, R6→09, R7/R8→07/11,
R9→03/04, R10→13, R11→10, R12→10, R13→07 §8.
