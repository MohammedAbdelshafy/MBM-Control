# 13 — Roadmap & Implementation Sequence

Status: APPROVED (Terminal 1) · Date: 2026-08-25
Rule: each milestone has a hard acceptance gate; no gate-jumping. Builder
(Terminal 2+ agents) implements ONE milestone at a time against these specs.

| # | Milestone | Content | Gate (evidence required) |
|---|---|---|---|
| M0 | Documentation baseline (THIS) | docs/contec/ 01–13 + DECISION_LOG | all files exist, cross-consistency check done |
| M1 | Reproducible environment | frappe_docker dev+staging compose, `contec` app skeleton, image build CI | clean-host install doc executed verbatim; app loads |
| M2 | Company configuration | CoA fixtures (07 §1), cost-center hook, EG VAT/WHT templates (placeholders confirmed by Chief), numbering series, print formats AR/EN | fixture import reproducible; sample JE balances |
| M3 | Users & security | 8 roles, 9+ users, User Permissions, workflows WF1–4, MFA on privileged, API guard hook | T-PERM suite green |
| M4 | Masters + opening balances | bilingual masters import templates, opening entries procedure executed in staging | TB variance=0 drill (07 §8) |
| M5 | Core finance cycles | P1 AP cycle + P2 AR cycle + payments + drawers P5 end-to-end | T-FIN,T-PAY green incl. golden T-GOLD |
| M6 | Projects & inventory | Project triad automation, stock flows P4, advances/claims P3 | T-PRJ,T-STK,T-ADV green |
| M7 | Data-entry hardening | Quick Entry forms, duplicate guard, bulk import pipeline, mobile timing pass | T-DE,T-IMP green; §timing targets met |
| M8 | Reporting pack | profitability, aging, cash position, budget-vs-actual, AR/EN print matrix | reports reconcile to GL on staging month |
| M9 | Ops hardening | backups+off-site, restore drills, monitoring/alerts, runbooks, UAT | go-live gate 10 §7 all checked |
| M10 | Pilot go-live | 1 real project live for 30 days with Chief Accountant shadow-close | success criteria S1–S7 (01 §6) evidenced |

## Phase-gated post-V1 tracks

| Track | Trigger | Notes |
|---|---|---|
| OCR extraction (09 §7 Phase 2) | after M7 stability | provider adapter + review UI; never auto-post (D-011) |
| ETA e-invoicing integration | legal mandate date + Chief confirmation | separate validated phase (D-012); build inside `contec`, study Odoo's open `l10n_eg_edi_eta` as REFERENCE ONLY |
| Budgets module | when GM demands | native Budget vs CC, configure-only |
| Assets & maintenance | register-level V1.1 | native Asset doctype |
| Payroll | explicit owner decision | hrms exists but OUT of V1 scope |

## Dependency rules for builder agents

1. Never edit erpnext/frappe/hrms sources (D-004); all changes in `apps/contec`.
2. Every milestone branch references this roadmap item + spec sections in PR body.
3. Financial code changes require failing-test-first (12 §4).
4. Any deviation = new DECISION_LOG entry BEFORE implementation.
