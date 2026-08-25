# PLATFORM BAKEOFF — Hands-On Verification Charter (M1 Gate)

Status: ACTIVE · Charter date: 2026-08-25 · Executor: OX2
Paper decision: D-001 (ERPNext v16). This charter makes the decision EARNED,
not assumed. **The platform remains UNCONFIRMED until this bake-off passes.**
Evidence rules: FACT requires command output / screenshot / file path recorded
in the result log. "It opened in a browser" is NOT a pass.

## 1. Environment under test

- Official frappe_docker tooling only (compose/pwd.yml-derived production-style
  stack or dev container per frappe_docker docs).
- ERPNext version-16 + matching Frappe + Frappe HR (hrms) version-16.
- Custom app skeleton `contec` installed into the bench (empty fixtures OK at M1).
- One site, administrator + seeded test users only. No business data yet.

## 2. Required scenarios (execute ALL; same data reused across them)

| # | Scenario | Pass criterion |
|---|---|---|
| S01 | Install reproducibility | clean-host install doc executes verbatim twice; second run identical result |
| S02 | Company + CoA + EGP | company created, posting works, GL balanced on sample JE |
| S03 | Project + Cost Center dimension | JE/SINV/PINV carry Project+CC; profitability query returns by CC |
| S04 | Customer + Sales Invoice + receipt | AR subledger reconciles to Debtors control |
| S05 | Supplier bill + payment (+partial pay) | AP reconciles; allocation correct |
| S06 | Employee Advance + settlement (hrms) | asset path posts; outstanding matches control account |
| S07 | Purchase material → receipt → stock issue to project | valuation lands on project MAT cost center |
| S08 | Expense claim flow w/ attachment | draft→approve→post; attachment stored private |
| S09 | 8+ users × role matrix negatives | denied actions actually deny server-side (06 §2 spot set) |
| S10 | Arabic UI + RTL + Arabic name search + AR print PDF | renders, searches normalized, PDF shapes correctly |
| S11 | English audit walk of same records | full traceability EN side |
| S12 | REST API read-only token | reads data; CANNOT submit/delete (guard verified) |
| S13 | Data Import 500-row supplier-bill CSV dry-run | row-level error report correct |
| S14 | Backup (`bench backup --with-files`) | artifact produced, checksummed |
| S15 | Restore into scratch environment | TB variance=0; one submitted invoice printable |
| S16 | Mobile browser (phone viewport) entry of one expense | usable ≤60s |
| S17 | Accounting integrity stress | forced imbalance attempt REJECTED by engine |

## 3. Gates

G1 All 17 scenarios executed with evidence logged.
G2 Any FAIL that touches accounting integrity, RBAC, or backup/restore =
   automatic OXYGEN RULE trigger → STOP → finding documented here → return to
   OX Alpha for platform review. NO silent redesign.
G3 Non-critical gaps (e.g., translation coverage %) are logged as RISKS with
   mitigation owner, not failures.
G4 Result file: `docs/contec/M1_BAKEOFF_RESULTS.md` committed by OX2 with
   scenario table + evidence links + versions (frappe/erpnext/hrms images).

## 4. Current status

| Item | Status |
|---|---|
| Charter issued | 2026-08-25 (OX Alpha) |
| Environment built | NOT STARTED |
| Scenarios executed | 0 / 17 |
| Platform confirmed | **NO — pending M1** |

Supersedes nothing. Feeds DECISION_LOG D-002/D-019.
