# 03 — ERP Platform Decision

Status: PENDING RESEARCH — NO WINNER DECLARED
Owner: Terminal 1 (research) / Terminal 2 (verification) / Operator (approval)
Last updated: 2026-08-25

## Rule

No platform is selected without: (a) completed desk research with primary
sources, (b) executed bake-off evidence per `PLATFORM_BAKEOFF.md`,
(c) OX2 verification, (d) operator sign-off recorded here and in
`DECISION_LOG.md`. Declaring ERPNext the winner by default is prohibited.

## Candidate register (open)

| # | Candidate | License | Desk-research | Bake-off run | Notes |
|---|-----------|---------|---------------|--------------|-------|
| 1 | ERPNext (Frappe) | UNVERIFIED here — T1 to cite LICENSE + repo | PENDING | NOT RUN | Mission brief names it first-choice-but-not-auto-selected |
| 2 | Odoo Community | UNVERIFIED | PENDING | NOT RUN | Module availability differs from Enterprise; verify exactly which modules are Community |
| 3 | Axelor Open Suite | UNVERIFIED | PENDING | NOT RUN | |
| 4 | Dolibarr | UNVERIFIED | PENDING | NOT RUN | Verify depth of projects/cost-center accounting |
| 5 | Tryton | UNVERIFIED | PENDING | NOT RUN | |
| 6 | Open Mercato | UNVERIFIED | PENDING | NOT RUN | Newer entrant; verify maturity + community health |
| 7 | iDempiere | UNVERIFIED | PENDING | NOT RUN | |
| 8 | Flectra | UNVERIFIED | PENDING | NOT RUN | Licensing model history requires verification |
| 9 | (reserved) other serious candidate found in research | — | — | — | Add rows as discovered |

License claims above are deliberately UNVERIFIED: this terminal will not state
licenses it has not checked at primary sources (project LICENSE files, official
licensing pages). Terminal 1 fills them with citations.

## Verification checklist (per finalist — OX2 responsibility)

For each finalist reaching hands-on evaluation, verify EVERY item and mark
FACT(cited)/UNVERIFIED:

- License + license-change risk history
- Self-hosting requirements (OS, DB, runtime versions)
- Accounting: double-entry GL, AR, AP, multi-currency, period close
- Projects, cost centers / analytic dimensions
- Procurement (PO→receipt→bill), Inventory incl. transfers, Assets + maintenance
- Expenses; employee advances (native or extension effort?)
- Subcontractor handling pattern
- Permissions/RBAC granularity; role-per-document-state rules
- API completeness (read AND write), API auth model, rate behavior
- Bulk data entry + CSV import quality (dry-run? error reporting?)
- Arabic UI quality + true RTL; English/LTR
- Mobile web usability (responsive vs separate app)
- Docker support OFFICIAL status (first-party images vs community)
- Backup/restore tooling (documented, scriptable)
- Extensibility mechanism (custom app/plugin WITHOUT core forks)
- Upgrade path safety (customizations survive upgrades?)
- Egyptian tax suitability (VAT config, formats); ETA e-invoicing feasibility
- AI-agent compatibility: stable read-only API for retrieval; webhook/API write
  paths that respect approval workflows

## Verification method

Primary sources first: official docs, official repos, release notes, official
pricing/licensing pages, Egyptian Tax Authority material. Marketing claims are
not facts. Every claim in the final decision record needs a URL + access date.
Where OX2 cannot reproduce a claim, the claim is flagged UNVERIFIED in
`DECISION_LOG.md` and blocks selection.

## Decision record (to be completed)

```
Selected platform:   PENDING DECISION
Version pinned:      —
Approval date:       —
Approved by:         —
Bake-off report:     — (link PLATFORM_BAKEOFF results section)
Dissent/opinions:    —
Falsification note:  any later-discovered disqualifier reopens this decision
```
