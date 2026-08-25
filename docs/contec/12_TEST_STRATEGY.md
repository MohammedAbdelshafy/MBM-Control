# 12 — Test Strategy

Status: APPROVED (Terminal 1) · Date: 2026-08-25
Principle: accounting invariants and permission negatives outrank UI polish.

## 1. Test layers

| Layer | Tooling | Scope |
|---|---|---|
| L1 unit | pytest, hermetic (no network) | duplicate_guard scoring, arabic_search normalization, threshold router, WHT/VAT template math wrappers |
| L2 platform tests | Frappe test framework (records + fixtures) | custom DocTypes validations, hooks (project→CC/WH creation), posting guard hook |
| L3 API/permission | pytest against staging REST | role matrix positives/negatives per 06 |
| L4 E2E UI | Playwright (desktop+mobile viewports, AR+EN) | entry flows P1–P7 happy paths |
| L5 ops drills | bash scripts | backup/restore, rollback, import batch |
| L6 UAT | scripted manual scenarios with Contec staff | sign-off before go-live |

## 2. Golden end-to-end scenario (must exist as automated L4 test)

T-GOLD "Arabic receipt → ledger → report":
1. Site Engineer (ar locale, phone viewport) photographs paper receipt.
2. Creates Contec Expense Voucher: amount 4,250.00, drawer, project PRJ-KASR,
   CC -MAT; attachment auto-added; duplicate guard runs.
3. Accountant (en locale) reviews, corrects account to Materials-Cement,
   confirms cost center, submits.
4. Assert GL Entry rows balanced; drawer account credited 4,250; expense debited
   4,250 on CC PRJ-KASR-MAT.
5. Project Profitability report includes it; Arabic print format renders RTL
   correctly (screenshot diff).

## 3. Acceptance catalog (each maps to requirement)

T-FIN (07): balanced posting for every pattern in §5 table; JE imbalance
impossible; cancel/amend lineage intact; period freeze blocks backdating;
WHT deducted and remittance JE correct.
T-PRJ: project creation spawns CC tree + warehouse (05 §3); misattribution
(project A doc on project B CC) rejected; HQ overhead requires reason code.
T-PAY: partial payments allocate; overpayment blocked w/o override; double
payment hard-blocked (09 §6); threshold WF-4b routes >50k to GM.
T-STK: receive→transfer→issue valuation posts to MAT CC; negative stock blocked;
reconciliation variance JE Chief-only.
T-ADV: advance→settlement full/partial→return paths post correctly; outstanding
report matches GL control account.
T-PERM (06): for each of 8 roles × key doctypes assert allowed AND denied
actions incl. API-token inheritance limits (I4); maker≠checker (I1).
T-I18N (08): normalization golden set {أحمد=احمد=آحمد; مبروك=مبارك? NO — ة→ه only,
ي cases; tatweel strip}; mixed bidi string renders unscrambled; AR PDF shaping;
label coverage ≥98% of visible chrome both locales (script counts untranslated).
T-DE (09): F1–F6 checks per screen; timing targets met on throttled 3G profile;
auto-save recovery; idempotent submit retry (same UUID no dupes).
T-IMP (09 §5): 5k-row supplier-bill dry-run report correctness; poisoned rows
rejected row-level; committed import enters as drafts only.
T-SEC (11): MFA enforced roles blocked without TOTP; private file URL anon
access denied; frozen-period unfreeze logged; secrets scan clean in CI.
T-OPS (10): nightly backup artifact verified; restore drill into scratch env:
row counts match + TB variance 0 + one submitted invoice printable; rollback tag
redeploy succeeds.

## 4. Regression policy

Any bug fix touching financial code ships with a failing-test-first commit.
Full L1–L3 suite green required before merge; L4 smoke subset before deploy.

## 5. Pre-go-live gate = T-FIN,T-PAY,T-PERM,T-I18N,T-GOLD,T-OPS all green on
staging with anonymized prod copy + L6 UAT signed by Owner & Chief Accountant.

## 6. Performance sanity

Simulate 15 concurrent users mixed profile (10 entry, 4 approve, 1 reporting)
for 30 min on staging-sized host: error rate <0.5%, p95 form-save ≤3s,
import job isolated on long worker.
