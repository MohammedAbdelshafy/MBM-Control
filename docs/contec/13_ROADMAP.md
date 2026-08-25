# 13 — Roadmap

Status: PROPOSED sequence (mission brief FACT for milestone list); dates deliberately omitted
Owner: OX Alpha sequencing / all terminals
Last updated: 2026-08-25

## Current position

```
M0  Governance & source-of-truth ........ IN PROGRESS (this branch)
BAKE-OFF Platform evaluation ............ BLOCKED-BY M0 completion → T1 research
```

## Milestone ladder (exit criteria bind)

| # | Milestone | Entry criteria | Exit criteria (summary) |
|---|---|---|---|
| M0 | Governance/docs/gates | directive issued | this doc set complete + gates defined + roles unambiguous |
| B/O | Bake-off | M0 done; T1 desk research with citations | ≥ top-3 candidates scored on all 34 scenarios; decision recorded per doc 03 |
| M1 | Foundation | platform selected+installed reproducibly | company/fiscal year/currency/CoA/cost centers/projects/customers/suppliers/banks/cash/taxes/users/roles configured + permission & accounting tests green |
| M2 | Accounting workflows | M1 | invoices/bills/payments/advances/expenses/JEs/opening balances + accounting suite green |
| M3 | Construction ops | M1 (can parallel M2 where independent) | projects/profitability/procurement/inventory/site stores/subcontractors/assets/maintenance |
| M4 | Management | M2+M3 data flowing | dashboards/profitability/cash/AR-AP aging/budget-vs-actual, provenance drill-down working |
| M5 | Contec UX | M2 (UX can start earlier on drafts) | AR/EN/RTL/LTR/mobile/fast-entry/search/attachments per docs 08/09 |
| GO | Go-live gate | Y4 restore drill passed + SECURITY_GATE all-critical PASS + QA_RELEASE_GATE GO | production live |

## Standing rules across all milestones

- Small coherent commits; never mix unrelated changes.
- CONFIGURE→EXTEND→BUILD discipline enforced at review.
- Any architectural problem discovered mid-milestone → STOP → record in
  `IMPLEMENTATION_BLOCKER.md` (append section) → resolve via DECISION_LOG.

## Immediate next actions

1. T1: desk research with primary-source citations for candidate register. [PENDING]
2. Operator: approve/deny dedicated `contec-erp` repository (D-010).
3. Operator/OX Alpha: reconcile terminal-role labels D-003.
4. After 1–3: provision identical Docker environments for bake-off candidates.
