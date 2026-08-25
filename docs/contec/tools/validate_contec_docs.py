#!/usr/bin/env python3
"""Contec source-of-truth documentation validator.

Verifies (offline, stdlib only):
  1. every required doc exists in docs/contec/
  2. each carries a Status line and Last-updated line
  3. evidence-marker vocabulary present where required
Exit code 0 = pass, 1 = failure. Safe read-only tooling (M0-authorized).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "01_BUSINESS_REQUIREMENTS.md": ["FACT", "PENDING RESEARCH"],
    "02_PROCESS_MAP.md": ["PROPOSED", "PENDING"],
    "03_ERP_PLATFORM_DECISION.md": ["PENDING RESEARCH", "UNVERIFIED"],
    "04_ARCHITECTURE.md": ["VERIFIED", "UNKNOWN", "NEEDS_REVIEW", "CONFLICT"],
    "05_DATA_MODEL.md": ["PROPOSED"],
    "06_USER_ROLES.md": ["PENDING DECISION"],
    "07_ACCOUNTING_RULES.md": ["DEBITS = CREDITS", "PENDING RESEARCH"],
    "08_ARABIC_ENGLISH_SPEC.md": ["RTL", "LTR"],
    "09_DATA_ENTRY_SPEC.md": ["DRAFTS", "DUPLICATE DETECTION", "BULK IMPORT"],
    "10_DEPLOYMENT_SPEC.md": ["restore", "backup", "HTTPS"],
    "11_SECURITY_SPEC.md": ["least privilege", "NO AUTONOMOUS DELETION"],
    "12_TEST_STRATEGY.md": ["Accounting", "Arabic", "Backup/Restore"],
    "13_ROADMAP.md": ["Bake-off", "M1"],
    "DECISION_LOG.md": ["APPEND-ONLY", "D-003"],
    "IMPLEMENTATION_BLOCKER.md": ["BLOCKED"],
    "OX_ALPHA_TRUST_AND_3_TERMINAL_RULES.md": ["Terminal 2"],
    "PLATFORM_BAKEOFF.md": ["34", "NO WINNER", "5 = native, mature, well tested"],
    "REPOSITORY_STRATEGY.md": ["contec-erp", "NOT APPROVED"],
    "SECURITY_GATE.md": ["NO-GO"],
    "QA_RELEASE_GATE.md": ["GO", "NO-GO"],
}

# Externally-owned documents (other terminals); header convention not enforced
# to avoid editing another terminal's work.
HEADER_EXEMPT = {"OX_ALPHA_TRUST_AND_3_TERMINAL_RULES.md"}

failures = []
for name, needles in sorted(REQUIRED.items()):
    path = ROOT / name
    if not path.is_file():
        failures.append(f"MISSING FILE: {name}")
        continue
    text = path.read_text(encoding="utf-8")
    if name not in HEADER_EXEMPT:
        if "Status:" not in text:
            failures.append(f"{name}: missing 'Status:' header line")
        if "Last updated:" not in text:
            failures.append(f"{name}: missing 'Last updated:' line")
    for needle in needles:
        if needle not in text:
            failures.append(f"{name}: required marker not found: {needle!r}")

if failures:
    print("VALIDATION FAILED:")
    for f in failures:
        print(" -", f)
    raise SystemExit(1)

print(f"VALIDATION PASSED: {len(REQUIRED)} documents checked, "
      f"{sum(len(v) for v in REQUIRED.values())} content assertions green.")
