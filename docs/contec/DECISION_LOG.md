# Contec ERP — Decision Log

Status: ACTIVE — APPEND-ONLY
Owner: OX Alpha maintains; all terminals append
Last updated: 2026-08-25

Rules:

1. Entries are append-only. Never rewrite history; supersede with a new entry.
2. Every entry must state its evidence class: FACT (verifiable record), PROPOSAL
   (not yet approved), PENDING DECISION, VERIFIED (evidence attached), UNVERIFIED.
3. No platform selection, permission matrix, or production deployment may be
   recorded as decided without evidence per `PLATFORM_BAKEOFF.md` /
   `SECURITY_GATE.md`.

## Log

| ID | Date | Decision / Finding | Class | Status | Decided by | Evidence |
|----|------|--------------------|-------|--------|-----------|----------|
| D-001 | 2026-08-25 | Contec ERP is a real accounting + construction ERP for an Egyptian construction company; zero software licensing cost; owner + ≥8 additional role-based users; Arabic+English first-class. V1 scope and exclusions as listed in `docs/CONTEC_ERP_AGENT_MISSION.md`. | FACT | ADOPTED | Operator (mission brief) | docs/CONTEC_ERP_AGENT_MISSION.md |
| D-002 | 2026-08-25 | Three-terminal model adopted by operator directive: T1 Architect/Researcher, **T2 Auditor/QA/Implementation Verifier (this terminal)**, T3 Builder. | FACT (directive) | ADOPTED | Operator | Operator directive 2026-08-25 §3 |
| D-003 | 2026-08-25 | **CONFLICT FLAGGED:** `docs/contec/OX_ALPHA_TRUST_AND_3_TERMINAL_RULES.md` (commit 12c3b48) labels T2=Builder, T3=Auditor — the inverse of D-002. Operator directive claims final authority; until reconciled, all Contec docs use the D-002 labels and refer to roles by name (Architect / Auditor / Builder), not only by number. | CONFLICT | OPEN — requires OX Alpha reconciliation | OX2 flagged | git 12c3b48 vs operator directive |
| D-004 | 2026-08-25 | Blockers B1–B4 confirmed valid by audit: B1 source-of-truth docs missing; B2 platform selection undocumented; B3 terminal role conflict (= D-003); B4 mixed-purpose repo unsuitable as clean ERP repo (~600 MB incl. build artifacts; full clones fail). | VERIFIED | CONFIRMED | OX2 audit | docs/contec/IMPLEMENTATION_BLOCKER.md |
| D-005 | 2026-08-25 | Milestone 0 scope = documentation/governance only. NO ERP implementation, NO accounting customization, NO migrations, NO production deployment, NO deletion of unrelated assets in this repository. | FACT (directive) | ADOPTED | Operator directive §22 | Operator directive 2026-08-25 |
| D-006 | 2026-08-25 | Platform decision is **NOT MADE**. Candidates remain open: ERPNext, Odoo Community, Axelor Open Suite, Dolibarr, Tryton, Open Mercato, iDempiere, Flectra + any serious candidate found during research. Winner may only be declared via the evidence process in `PLATFORM_BAKEOFF.md`. | PENDING DECISION | OPEN | T1 researches → OX2 verifies → Operator approves | PLATFORM_BAKEOFF.md |
| D-007 | 2026-08-25 | Trust-state vocabulary adopted system-wide: VERIFIED / UNVERIFIED / CONFLICT / NEEDS_REVIEW / UNKNOWN, with transition rules per §8 of operator directive and `04_ARCHITECTURE.md`. | FACT (directive) | ADOPTED | Operator directive §8 | 04_ARCHITECTURE.md |
| D-008 | 2026-08-25 | Accounting immutability policy adopted: posted records are never silently edited or deleted; corrections only via reversal / correction entry / controlled cancellation / controlled amendment workflow. Normal users cannot delete posted financial transactions. | FACT (directive) | ADOPTED | Operator directive §10; OX_ALPHA rules | 07_ACCOUNTING_RULES.md |
| D-009 | 2026-08-25 | Document-deletion policy adopted: NO AUTONOMOUS DELETION. Archive → revoke visibility → retention → controlled administrative deletion only when legally/operationally appropriate. Every destructive action requires actor, timestamp, reason, object, audit event. AI has no autonomous deletion authority. | FACT (directive) | ADOPTED | Operator directive §11 | 11_SECURITY_SPEC.md |
| D-010 | 2026-08-25 | Repository strategy: dedicated clean `contec-erp` repository RECOMMENDED; creation awaits explicit operator authorization. Current repo remains the planning home meanwhile. | PROPOSAL — NOT APPROVED | PENDING OPERATOR APPROVAL | OX2 recommends | REPOSITORY_STRATEGY.md |
| D-011 | 2026-08-25 | Bilingual architecture: one canonical data store; localized UI; no separate per-language databases. Arabic entity names (customer/supplier/project/notes/attachment metadata) must survive language switching intact. | FACT (directive) | ADOPTED | Operator directive §13 | 08_ARABIC_ENGLISH_SPEC.md |
| D-012 | 2026-08-25 | Authentication foundation required from first implementation milestone; ~10-user capability architecture now, detailed matrix later. No real passwords ever committed to Git. | FACT (directive) | ADOPTED | Operator directive §12 | 06_USER_ROLES.md, 11_SECURITY_SPEC.md |
