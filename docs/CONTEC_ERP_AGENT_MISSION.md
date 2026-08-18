# Contec ERP: Zero-Cost Odoo Replacement — RESEARCH + DEPLOYMENT MISSION

## Objective
Build and deploy Contec Construction OS for an Egyptian construction company using an open-source ERP foundation, with zero software licensing cost and support for at least 8 additional users besides the owner/developer.

This is explicitly a **RESEARCH + BUILD + DEPLOYMENT** mission. Do not stop at architecture, recommendations, prototypes, or code. The final objective is a tested, accessible production deployment.

## Strategic direction
Use **ERPNext/Frappe as the first-choice foundation**, but do not treat it as automatically selected. Research the current 2026 alternatives first and run the practical bake-off. Keep the architecture upgrade-safe and use a separate Contec custom app for company-specific workflows.

Do NOT build a new accounting engine unless research proves the selected platform cannot safely provide the required capability.

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
- At least 8 additional role-based users besides owner/developer
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
1. Inspect native functionality.
2. If it already works, configure it.
3. If it partially works, extend it through supported mechanisms.
4. Only build new functionality when genuinely necessary.

Never modify ERP core unless unavoidable and documented.

## REQUIRED RESEARCH PHASE — MUST HAPPEN BEFORE MAJOR BUILD
Research current 2026 versions, licensing, architecture, capabilities, community health, documentation, deployment requirements, AI-agent compatibility, Egyptian localization/tax readiness, and total cost for at least:
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
- any materially relevant 2026 open-source ERP competitor discovered during research

Use primary sources first: official documentation, official repositories, licensing pages, release notes, official pricing, and Egyptian Tax Authority material. Distinguish FACT from marketing claims and inference.

Produce before major implementation:
- ARCHITECTURE.md
- CONFIGURE_EXTEND_BUILD.md
- ACCOUNTING_CONTROL_MATRIX.md
- SECURITY_MODEL.md
- TEST_PLAN.md
- IMPLEMENTATION_PLAN.md
- PLATFORM_BAKEOFF.md
- DEPLOYMENT_PLAN.md
- COST_MODEL.md

## PLATFORM BAKE-OFF
For the top 2–3 candidates, execute the same real Contec scenarios:
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

Select a winner based on evidence, not popularity. Do not automatically choose ERPNext.

## USER ROLES
- Owner / Director
- General Manager
- Chief Accountant
- Accountant
- Project Manager
- Site Engineer
- Procurement Officer
- Storekeeper
- Additional roles as justified

Enforce least-privilege permissions. No blanket Administrator access for normal users.

## CONSTRUCTION WORKFLOW
Project → Contract → Cost Center → Revenue + Expenses + Procurement + Inventory + Subcontractors + Payments → Project Profitability

## AI-AGENT SAFETY
AI may analyze, summarize, search, draft, and recommend. Financial posting, payment execution, tax submission, permission changes, production deployment, and destructive operations require explicit human authorization.

## DEPLOYMENT IS A REQUIRED DELIVERABLE
The project is NOT complete when code is merely committed to GitHub.

The agents must take the selected platform through:

1. Local development deployment.
2. Clean installation from documented instructions.
3. Production-like staging deployment.
4. Database initialization/migrations.
5. Creation of the Contec company/site.
6. Creation of all required roles.
7. Creation of at least 8 additional test users.
8. Configuration of permissions.
9. Configuration of accounting/project settings.
10. Configuration of backups.
11. Restore test into a clean environment.
12. HTTPS configuration.
13. Public remote-access configuration.
14. Mobile browser verification.
15. Smoke tests for core workflows.
16. Accounting reconciliation tests.
17. Security/permission tests.
18. Performance sanity test for 8+ users.
19. Rollback procedure test.
20. Production go-live checklist.

## PRODUCTION ACCESS
The target is one web application accessible to the owner plus at least 8 additional users from office PCs, laptops, tablets, and phones.

Preferred deployment order:

### Option A — Existing Contec server/PC
Use suitable existing hardware if it can provide reliable uptime, backups, and network connectivity.

### Option B — Genuinely free cloud compute
Evaluate current free cloud offerings. If used, verify current limits, regional capacity, account requirements, persistence, backup options, and terms. Never claim a free tier is guaranteed forever.

### Option C — Low-cost VPS fallback
If zero-cost infrastructure is unreliable, document the cheapest practical production VPS as the fallback. Software licensing must remain zero.

Do not make Cloudflare, Oracle, Supabase, or any other provider a hard dependency until current capabilities and limits are verified.

## PUBLIC WEB ACCESS
Use HTTPS. A tunnel/reverse proxy such as Cloudflare may be evaluated for the public front door, but the deployment must remain secure if the tunnel is unavailable.

Do not expose database ports directly to the public Internet.

## BACKUPS
Production requires:
- automated database backup
- attachment/file backup
- backup rotation
- off-site encrypted copy where practical
- restore procedure
- documented recovery steps
- successful restore test before Go-Live

A backup that has never been restored is not considered verified.

## SECURITY
Implement and verify:
- RBAC
- server-side authorization
- secure sessions
- MFA where supported
- audit logs
- secret management
- HTTPS
- attachment permissions
- database access controls
- least privilege
- patch/update process
- vulnerability review

## DEPLOYMENT ARTIFACTS
Create and maintain:
- Docker/deployment configuration where practical
- .env.example with NO real secrets
- deployment documentation
- backup scripts/configuration
- restore documentation
- health checks
- smoke-test script
- production checklist
- rollback instructions
- user onboarding instructions
- admin runbook

Never commit passwords, API keys, tax credentials, certificates, private keys, or production secrets.

## AI DEVELOPMENT MODEL STRATEGY
Primary coding model: **Qwen3-Coder** when a reliable free endpoint is available.

Reasoning/review model: **GPT-OSS-120B** or another strong free reasoning model available through the configured provider.

Fast worker/test model: **Nemotron 3 Nano** or comparable free coding/agent model.

Fallback: provider free-model router or strongest currently available free coding model.

Never hard-code a single provider as the only dependency. Maintain model fallback configuration.

## 2-TERMINAL OPERATING MODEL
### Terminal 1 — BUILDER
Role: primary implementation + deployment agent.
Responsibilities:
- inspect repository and selected ERP
- implement one bounded milestone at a time
- write tests
- run migrations/tests
- prepare deployment
- deploy to staging
- verify health
- commit cleanly
- never touch unrelated files

Preferred free model: Qwen3-Coder.

### Terminal 2 — AUDITOR / QA / RELEASE GATE
Role: independent reviewer, breaker, and deployment verifier.
Responsibilities:
- inspect Terminal 1 changes
- challenge architecture
- verify accounting entries and permissions
- find regressions
- write missing tests
- validate migrations
- test backup/restore
- test security
- verify staging deployment
- verify production readiness
- reject unsafe changes

Preferred free model: GPT-OSS-120B or strongest available free reasoning/coding model.

The auditor must not rubber-stamp the builder.

## FIRST MILESTONE
Do not implement the ERP yet.

Complete the research and bake-off first, then install the selected winner in a reproducible development/staging environment.

Only after the winner is proven should major Contec customization begin.

## DEPLOYMENT GATE
Before declaring Go-Live, prove all of the following:

- selected platform is documented
- installation is reproducible
- 8+ user accounts work
- roles/permissions work
- accounting transactions balance
- core Contec workflows work
- mobile browser works
- backups run
- backup restore succeeds
- HTTPS works
- secrets are not in Git
- production health check passes
- rollback is documented
- administrator runbook exists
- user onboarding guide exists
- current Git state is clean/understood

## DEFINITION OF DONE
A feature is only complete when implementation, permissions, migration, tests, accounting effects, failure cases, documentation, and git state have all been verified.

A deployment is only complete when the application is actually running in the target environment and independently verified by the Auditor terminal.

## CRITICAL RULE
Optimize for maximum business functionality with minimum new code, while preserving accounting integrity, security, maintainability, upgradeability, data ownership, zero licensing cost, and a real working deployment.
