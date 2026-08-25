# 03 — ERP Platform Decision

Status: DECIDED (Terminal 1) · Date: 2026-08-25 · Decision IDs: D-001, D-002
Evidence standard: official docs/repos/licenses only; FACT vs INFERENCE labeled.

## 1. Winner: **ERPNext v16 (Frappe framework), self-hosted via frappe_docker**

- ERPNext `version-16` branch, license file `license.txt` = GNU GPL v3
  (verified in repo root: https://github.com/frappe/erpnext/blob/version-16/license.txt,
  35KB GPL text; latest release line v16.32.x, Aug 2026).
- Frappe framework + hrms same GPL family. Commercial self-hosted multi-user
  internal use: permitted, zero license fee.
- Contec-specific behavior goes into a SEPARATE custom Frappe app (`contec`)
  — core is never patched (D-004).

## 2. Bake-off evidence table (primary sources)

| Candidate | License | Double-entry GL | Project/Cost-center dimensions | AR/AB+RTL | Procurement+Inventory | Advances/Expenses | Docker story | API/Import | Audit | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **ERPNext v16** | GPL-3 ✔ verified | STRONG (GL/JE/PE core) | BUILT-IN (Project + Cost Center on transactions; custom Accounting Dimensions) | MEDIUM–STRONG (Crowdin-managed ar translations; RTL desk) | YES core | YES hrms `Employee Advance`, `Expense Claim` ✔ verified | OFFICIAL frappe_docker docs tree ✔ | Auto REST API + Data Import | Version/Access/Activity logs | **WINNER** |
| Odoo Community 19 | LGPL-3 | WEAK — full accounting app is Enterprise-only (editions matrix); analytic addon present but ledger paywalled | MEDIUM | STRONG | YES | Expenses Community, payroll Ent | Strong | JSON-RPC | mail.thread only; approvals Enterprise | Runner-up ONLY if paid Enterprise accepted → violates R11 |
| Axelor Open Suite 9 | AGPL-3 | STRONG core (`axelor-account`) | STRONG (`axelor-project`,`-budget`) | UNKNOWN — no primary evidence | YES | YES (`axelor-human-resource`) | No official image verified | REST (vendor docs) | Unverified | AGPL + Arabic unknown = integration risk too high for V1 |
| Dolibarr 24 | GPL-3 | MEDIUM (`htdocs/accountancy`) | WEAK-MEDIUM project costing | STRONG (`langs/ar_SA` shipped) | YES | Expense reports YES | Official docker org | Core REST | blockedlog immutable log | Fails R7 depth for construction cost control |
| Tryton 8 | GPL-3 | STRONG multi-axis analytic | STRONG | WEAK/UNKNOWN | YES | No first-party advances found | Official image | JSON-RPC | Model history opt-in | Arabic greenfield → time-to-value fail |
| iDempiere 13 | GPL-2 | STRONGEST (multi set-of-books) | STRONGEST dimensions | WEAK evidence | YES | Basic | No canonical official image | Jersey REST | Mature audit | Complexity/UI tax unacceptable for bilingual field rollout |
| Flectra 3 | LGPL-3 (Odoo fork) | inherited stale | inherited | UNKNOWN | yes | yes | none verified | — | — | DORMANT (last upstream commits Apr 2025; site transport error). EXCLUDED |
| Open Mercato | MIT | NONE — it is an AI-engineering framework, not a ledger | N/A | UNKNOWN | no | no | yes (framework) | yes | n/a | Too young; watch-list only (D-018) |
| metasfresh | GPLv2 mixed ecosystem | STRONG | MEDIUM | UNKNOWN | YES | basic | docker exists | REST | legacy | Releases invisible on GitHub since 2023 → opaque ops risk |
| Apache OFBiz 24 | Apache-2.0 | toolkit-grade | WEAK | none evidenced | DIY | DIY | manual | — | — | A toolkit, not a deployable product |

Sources: odoo.com/page/editions + odoo/LICENSE (LGPL-3) + odoo addons/l10n_eg_edi_eta
(present in community repo but presumes enterprise accounting around it);
axelor-open-suite/LICENSE (AGPL-3); Dolibarr repo dirs htdocs/accountancy,
htdocs/projet, langs/ar_SA, htdocs/blockedlog; tryton.org/download + PyPI
trytond-analytic-account ("multiple different axes"); idempiere.org homepage
("multiple sets of books"); flectra-hq/flectra LICENSE + commit history;
open-mercato/open-mercato LICENSE (MIT, "AI-Engineering Foundation Framework");
metasfresh LICENSE.md + releases page; ofbiz.apache.org.

## 3. Why ERPNext won (decision rationale)

W1. Only candidate satisfying ALL of: open double-entry GL + built-in Project and
    Cost Center accounting dimensions on every transaction + procurement +
    inventory + employee advances/expenses + granular role/workflow permissions
    + auto REST API + CSV/XLSX import + official Docker deployment — under a
    single GPL codebase with zero license cost (R7, R9, R11).
W2. Permission model matches the approval problem exactly: DocType-level
    read/create/write/submit/cancel/amend per role + record-level User
    Permissions + Workflow states/actions → implements 06_USER_ROLES without code.
W3. Submitted documents become immutable; corrections happen via cancel/amend —
    the audit posture a contractor's books need (07 §2).
W4. `Employee Advance` and `Expense Claim` ship in frappe/hrms v16 (verified),
    covering P3 cycle without custom finance logic.
W5. Translation infrastructure (crowdin.yml verified in erpnext v16) gives AR UI
    coverage we can top up locally; RTL desk layout supported.
W6. Active 2026 development (v16.32.x Aug-2026) → patchability and hiring pool.

Honest negatives recorded (not disqualifying): Arabic translation gaps will need
local CSV top-ups; Desk is responsive but not a native mobile UX; Egypt regional
module ABSENT from ERPNext v16 core (verified listing of `erpnext/regional/`:
address_template, australia, italy, south_africa, turkey, UAE, US — no egypt)
→ Egyptian VAT templates, WHT templates and any future ETA integration are OUR
responsibility inside the `contec` custom app (D-005, D-012).

## 4. Runner-up and exit strategy

Runner-up: Odoo (Community + OCA assembly, or paid Enterprise if owner ever
approves licensing budget). Exit insurance: all masters maintained as clean
CSV/XLSX exports (Data Import-compatible), monthly full DB dump, attachments on
plain disk — migration data always extractable. Switching cost accepted as
lower than building on an unproven stack.

## 5. Rejection consequences (binding on builders)

- No Odoo modules may be introduced. No second accounting engine beside GL.
- Any claim "ERPNext supports X" must cite doctype/doc path at implementation review.
- Egyptian tax features MUST be built as `contec` app fixtures/templates,
  never by editing erpnext files (D-004).
