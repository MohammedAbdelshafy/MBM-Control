# 06 — User Roles & Permission Matrix

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-007, D-008
Mechanism: Frappe Role + DocType permission (read/write/create/submit/cancel/
amend) + User Permissions (record scoping) + Workflow states. No blanket admin.

## 1. Role registry

| Role code | Frappe Role | Count | Scope |
|---|---|---|---|
| OWNER | Contec Owner | 1 | all projects, read-everything, approve |
| GENERAL_MANAGER | Contec GM | 1–2 | all projects, approve within limits |
| CHIEF_ACCOUNTANT | Contec Chief Accountant | 1 | all financial, journals, close |
| ACCOUNTANT | Contec Accountant | 2–3 | entry+submit AP/AR/payments |
| PROJECT_MANAGER | Contec Project Manager | 1–2 | own project(s) only |
| SITE_ENGINEER | Contec Site Engineer | 2–4 | own project data entry |
| PROCUREMENT_OFFICER | Contec Procurement | 1–2 | PO lifecycle |
| STOREKEEPER | Contec Storekeeper | 2–4 | own warehouse(s) |
| SYSTEM_ADMIN | System Manager | owner+developer ONLY | platform config |

`System Manager` is NEVER assigned to business roles (D-008). Developer's daily
account uses a role with no financial submit rights; developer acts through
staging or via explicit owner-approved elevation window (logged).

## 2. Permission matrix — core document groups

Legend: R=read C=create W=edit(own drafts) S=submit X=cancel A=approve(workflow)
E=export ●=full –=none. "(P)" = restricted to own project via User Permission;
"(W)" = restricted to own warehouse.

| Doc group | OWNER | GM | CHIEF | ACCT | PM(P) | SITE(P) | PROC | STORE(W) |
|---|---|---|---|---|---|---|---|---|
| Company/CoA settings | R | R | RW | R | – | – | – | – |
| Customer/Supplier masters | R | R | RCW | RCW | R | R | RCW | R |
| Item/Warehouse masters | R | R | RCW | RCW | R | R | RCW | CW |
| Project/Cost Center | RCWX | RCWX | RCW | R | R(P) | R(P) | R | R(W) |
| Purchase Order | R | RSA | RSA | RS | RC | RC | RCWS | R |
| Purchase Receipt | R | R | R | RS | R | C | R | RCWSX |
| Purchase Invoice | R | RA | RCSAX | RCWS | R | – | R | – |
| Sales Invoice | R | RA | RCSAX | RCWS | RC | – | – | – |
| Payment Entry ≤ threshold* | R | RA | RCSAX | RCWS | – | – | – | – |
| Payment Entry > threshold* | RA | RA | RCSA | RC | R | – | – | – |
| Journal Entry | R | R | RCSAX | – | – | – | – | – |
| Expense Voucher (petty cash) | R | RA | RSAX | RCS | RC | RC | – | – |
| Employee Advance | R | RA | RSAX | RCS | RC | RC | – | – |
| Expense Claim | RA | RA | RSAX | RCWS | RCWS | RC | – | – |
| Stock Entry | R | R | R | R | R(P) | RC(P) | – | RCWSX |
| Stock Reconciliation | R | R | RA | R | R | – | – | RCWS |
| Contec Contract | RCWX | RCWX | RW | R | R(P) | R(P) | R | – |
| Contec Document (OCR file) | R | R | RWX | RCWS | RC | RC | RC | RC |
| Budget | RA | RA | RCW | R | RC(P) | – | – | – |
| Reports (GL, AR/AP aging, profitability) | RE | RE | RE | RE | RE(P) | RE(P) | RE | RE(W) |
| Users/Roles/Backups/System | – | – | R | – | – | – | – | – |

\* thresholds defined in 07 §7 (default: >EGP 50,000 single payment needs GM or
Chief approval workflow step; configurable fixture).

## 3. Workflow gates (enforced by Frappe Workflow, not convention)

WF-1 Purchase Order: Draft → Pending Approval → Approved → Ordered → Closed/Billed.
    Approver roles: CHIEF, GM (PROC submits for approval).
WF-2 Purchase Invoice: Draft → Under Review → Approved(ACCT submit) → Submitted.
    Reviewer ≠ creator rule enforced by workflow transition condition.
WF-3 Expense Voucher / Advance: Draft → Site Submit → Accountant Review → Posted.
WF-4 Payment Entry: per threshold routing WF-4a (≤thr: ACCT direct submit)
    and WF-4b (>thr: ACCT → GM/CHIEF approve → submit).
WF-5 Period close checklist tracked in custom `Contec Close Checklist` (V1.1).

## 4. Record-level scoping (User Permissions)

- PM/SITE: `Project = <assigned>` (+ derived cost centers).
- STORE: `Warehouse = <assigned>`.
- ACCT: unscoped (needs full books). GM/OWNER: unscoped.
Applies to lists, reports and API equally (server-side enforcement).

## 5. Maker-checker invariants (testable)

I1 No role can SUBMIT and APPROVE the same workflow instance.
I2 Journal Entry create+submit exists ONLY on CHIEF (single keyholder).
I3 Cancel of submitted financial doc requires CHIEF (or GM for non-journal docs
   below threshold), always logged to Access Log.
I4 API tokens inherit a human's roles; no token carries System Manager (11 §7).
