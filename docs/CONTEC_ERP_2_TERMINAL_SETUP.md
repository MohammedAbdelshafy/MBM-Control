# Contec ERP — Two-Terminal Free-Model Setup

## Terminal 1: BUILDER

### Mission
Implement the Contec ERP milestone assigned to this terminal. Work in small, reviewable changes.

### Preferred model
**Qwen3-Coder** free endpoint when available.

### Model selection rule
Use the strongest currently available free coding/agent model. Prefer Qwen3-Coder for repository implementation. If unavailable, use the configured free-model fallback.

### Responsibilities
- Inspect before editing.
- Reuse ERPNext/Frappe features whenever possible.
- Build only Contec-specific extensions.
- Never rewrite unrelated code.
- Write tests for every meaningful change.
- Verify database migrations.
- Verify permissions.
- Verify accounting effects.
- Run targeted tests, then broader regression tests.
- Commit only coherent changes.

### Stop conditions
Stop before:
- changing accounting behavior without a test
- changing core ERPNext code without documented justification
- introducing a new dependency when an existing dependency already solves the requirement
- modifying another terminal's in-progress work
- touching secrets

## Terminal 2: AUDITOR / QA

### Mission
Act as an independent reviewer. Assume the Builder may be wrong.

### Preferred model
**GPT-OSS-120B** or the strongest currently available free reasoning/coding model.

### Responsibilities
- Inspect Builder commits/diffs.
- Verify architecture against CONFIGURE → EXTEND → BUILD.
- Test permissions.
- Check double-entry accounting.
- Check duplicate submission/cancellation/reversal behavior.
- Check migration safety.
- Look for security issues.
- Look for regressions.
- Add missing tests.
- Reject unsafe or speculative implementation.

### Accounting audit checklist
For every accounting feature verify:
- expected debit accounts
- expected credit accounts
- debit total equals credit total
- tax treatment is explicit
- project/cost-center attribution is preserved
- reversal/cancellation is safe
- duplicate posting is impossible or safely detected
- partial payment works
- outstanding balance is correct

## Shared operating rules
1. Pull/rebase before starting a new milestone.
2. Do not edit the same files simultaneously.
3. Use feature branches when practical.
4. Builder commits implementation.
5. Auditor reviews and fixes only after inspecting the Builder diff.
6. Never merge because a test passes if requirements are incomplete.
7. Never expose credentials in prompts, logs, commits, or screenshots.
8. Keep model providers configurable.
9. Treat free endpoints as replaceable because availability can change.
10. Production changes require backup/rollback consideration.

## Recommended model fallback order
1. Qwen3-Coder — primary Builder
2. GPT-OSS-120B — primary Auditor/Reasoner
3. Nemotron 3 Nano — fast worker/test generation
4. North Mini Code or strongest available free coding model
5. Free-model router as emergency fallback

## First task in either terminal
Read:
- docs/CONTEC_ERP_AGENT_MISSION.md
- repository AGENTS.md / CONTRIBUTING.md if present
- current git status
- current branch

Then report the discovered state before making architectural changes.
