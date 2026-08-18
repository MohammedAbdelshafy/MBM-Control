# Contec ERP: Zero-Cost Odoo Replacement Agent Mission

## Objective
Build Contec Construction OS for an Egyptian construction company using an open-source ERP foundation, with zero software licensing cost and support for at least 8 additional users besides the owner/developer.

## Current strategic direction
Use **ERPNext v16/Frappe as the first-choice foundation**, but do not treat it as automatically selected. Keep the architecture upgrade-safe and use a separate Contec custom app for company-specific workflows.

Do NOT build a new accounting engine unless research proves the platform cannot safely provide the required capability.

## V1 scope
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
- 8+ role-based users
- Arabic + English responsive web UI
- Audit trail and approval controls
- Opening balances, not historical transaction migration
- Egyptian tax configuration, with ETA integration treated as a separate validated phase

## Explicitly excluded from V1
- BOQ
- Quantity measurement engine
- BOQ-based progress certificates
- Full custom ERP rebuild

## Principle: CONFIGURE → EXTEND → BUILD
For every requested feature:
1. Inspect native ERPNext/Frappe functionality.
2. If it already works, configure it.
3. If it partially works, extend it through supported app/doctype/hooks mechanisms.
4. Only build a new module when the requirement genuinely is not covered.

Never modify ERPNext core unless unavoidable and documented.

## User roles
- Owner / Director
- General Manager
- Chief Accountant
- Accountant
- Project Manager
- Site Engineer
- Procurement Officer
- Storekeeper
- Quantity Surveyor (optional even though BOQ is excluded; use only for document/cost responsibilities that actually exist)

Enforce least-privilege permissions. No blanket Administrator access for normal users.

## Construction workflow
Project → Contract → Cost Center → Revenue + Expenses + Procurement + Inventory + Subcontractors + Payments → Project Profitability

## AI-agent safety
AI may analyze, summarize, search, draft, and recommend. Financial posting, payment execution, tax submission, permission changes, and destructive operations require explicit human authorization.

## Production requirements
- Web-based, responsive desktop/tablet/mobile access
- HTTPS
- Role-based access control
- Audit logs
- Secure secrets handling
- Automated database and attachment backups
- Restore testing before production declaration
- Dockerized/reproducible deployment where practical
- No vendor lock-in

## Zero-cost infrastructure target
Prefer:
1. Existing Contec server/PC if suitable, or
2. A genuinely free cloud compute option when available, with local/off-site backups.

Cloudflare can be used as the public HTTPS/tunnel/front-door layer where appropriate. Do not confuse free software with free infrastructure: document every recurring cost honestly.

## Required research before major implementation
Compare at least:
- ERPNext
- Odoo Community / Enterprise
- Axelor Open Suite
- Dolibarr
- Tryton
- Open Mercato
- iDempiere
- metasfresh
- Apache OFBiz
- Flectra
- any materially relevant 2026 open-source ERP competitors

Evaluate accounting, construction/project fit, procurement, inventory, assets, subcontracting, permissions, APIs, AI-agent compatibility, licensing, hosting, Egyptian tax/localization, documentation, maintainability, and total cost.

Run a practical bake-off for finalists using these scenarios:
1. Project + cost center
2. Customer
3. Supplier
4. Supplier bill + payment
5. Customer invoice + receipt
6. Employee advance + settlement
7. Purchase material + receipt
8. Issue material to project
9. Project expense
10. Project profitability
11. P&L
12. Balance sheet
13. AR aging
14. AP aging
15. 8+ users and permissions
16. Mobile browser
17. Backup
18. Restore
19. API access
20. AI retrieval of business data

## AI development model strategy
Primary coding model: **Qwen3-Coder** when a reliable free endpoint is available.

Reasoning/review model: **GPT-OSS-120B** or another strong free reasoning model available through the configured provider.

Fast worker/test model: **Nemotron 3 Nano** or comparable free coding/agent model.

Fallback: provider free-model router or the strongest currently available free coding model.

Never hard-code a single provider as the only dependency. Maintain model fallback configuration.

## 2-terminal operating model
### Terminal 1 — BUILDER
Role: primary implementation agent.
Responsibilities:
- inspect repo
- inspect ERPNext/Frappe
- implement one bounded milestone at a time
- write tests
- run migrations/tests
- commit cleanly
- never touch unrelated files

Preferred free model: Qwen3-Coder.

### Terminal 2 — AUDITOR / QA
Role: independent reviewer and breaker.
Responsibilities:
- inspect Terminal 1 changes
- challenge architecture
- verify accounting entries and permissions
- find regressions
- write missing tests
- validate migrations
- check security and data integrity
- reject unsafe changes

Preferred free model: GPT-OSS-120B or strongest available free reasoning/coding model.

The auditor must not rubber-stamp the builder.

## First milestone
Do not implement the ERP yet.

First produce:
- ARCHITECTURE.md
- CONFIGURE_EXTEND_BUILD.md
- ACCOUNTING_CONTROL_MATRIX.md
- SECURITY_MODEL.md
- TEST_PLAN.md
- IMPLEMENTATION_PLAN.md
- PLATFORM_BAKEOFF.md

Then install/prototype the top 2–3 candidates and execute the 20-scenario bake-off.

## Definition of done
A feature is only complete when implementation, permissions, migration, tests, accounting effects, failure cases, documentation, and git state have all been verified.

## Critical rule
Optimize for maximum business functionality with minimum new code, while preserving accounting integrity, security, maintainability, upgradeability, data ownership, and zero licensing cost.
