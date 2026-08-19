# MBM Dialer Recovery Prompt

## Mission

You are the implementation agent for the MBM Dialer P0 recovery. The founder has been trying to update the live dialer for days. Do not produce another documentation-only fix. Trace the real production path, repair it, deploy it, and prove the browser is serving the newest canonical lead dataset.

Workspace:

`C:\Users\omare\OneDrive\Desktop\AI`

Live:

`https://mbm-dialer.higgsfield.app/`

Primary tracking issue:

`base44-app #7`

Related deployment repository:

`MohammedAbdelshafy/mbm-dialer`

## Absolute rules

1. Never assume the current directory. Verify the workspace before MBM commands.
2. Never assume `base44-app` is the deployment source. Prove which repo/project powers the live URL.
3. Never treat a local JSON/CSV change as a successful sync.
4. Never commit secrets or unnecessary raw private lead exports.
5. Never wipe dispositions, notes, attempts, stages, outcomes, verification state, or priority.
6. Never fabricate ownership, distress, property facts, prices, relationships, or motivation.
7. Do not create a second orchestrator or parallel sync system. Repair/reuse the canonical pipeline.
8. Do not mark complete until the live browser/runtime is verified.

## Execution order

### 1. Production forensics first

Determine and record:

- deployment repository
- deployment branch
- deployment provider/project
- latest deployed revision
- build/deploy path
- runtime data source
- API/static-data endpoint used by the browser
- exact file/table/API producing visible leads

Save a non-PII report to:

`MBM/Artifacts/GTM/dialer-production-forensics.json`

### 2. Audit the entire pipeline

Trace:

`source -> verification -> normalization -> dedupe -> classification -> scoring -> script generation -> dialer export -> deployment -> live runtime`

Search all relevant locations and scheduled jobs for:

`leads_database`, `dialer`, `reconcile`, `promote`, `push_top_100`, `seller`, `buyer`, `distress`, `Call_Script`, `category`, `vertical`, `verified`, `phone`, `deployment`.

Classify scripts/jobs as canonical, duplicate, obsolete, deployment, transform, verification, or unknown. Do not delete blindly.

### 3. Establish one canonical sync path

Implement/reuse one safe workflow:

`discover -> verify -> normalize -> dedupe -> classify -> score -> generate script -> reconcile -> publish -> deploy -> verify-live`

Expose equivalent behavior to:

- `dialer-sync --dry-run`
- `dialer-sync --apply`
- `dialer-sync --verify-live`

If the repository already has an established CLI, integrate with it instead of inventing another interface.

### 4. Repair lead semantics

Canonical categories:

- `REAL_ESTATE_SELLER`
- `REAL_ESTATE_BUYER`
- `WHOLESALER`
- `CLINIC`
- `GENERAL`

Segments may include:

- `DISTRESSED_SELLER`
- `ABSENTEE_OWNER`
- `VACANT_PROPERTY`
- `HIGH_EQUITY`
- `FREE_AND_CLEAR`
- `TIRED_LANDLORD`
- `OUT_OF_STATE_OWNER`
- `LIKELY_TO_MOVE`

`Distressed Property` is a source/property signal, not a fake company name and not a substitute for seller classification.

A distressed-property contact becomes a seller only when the available evidence supports seller/owner relevance. Missing evidence goes to `HUMAN_REVIEW` rather than invented facts.

### 5. Normalize and dedupe

Normalize US phones to `+1XXXXXXXXXX`.

Primary dedupe: normalized phone.
Secondary: name + property address.
Tertiary: name + mailing address.

Merge stronger incoming data without destroying historical call state.

Active calling queues must have zero duplicate normalized phones.

### 6. Repair scripts

Find the actual script generator. Scripts must use real lead/property context.

Never invent:

- ownership
- distress
- property details
- prices
- mortgage facts
- motivation
- relationships

If required context is missing, set `HUMAN_REVIEW`.

Script category must match lead category.

### 7. Ranking

Within each category prioritize:

1. verified usable phone
2. qualification score
3. confidence
4. motivation/distress evidence
5. lead score
6. freshness

New, verified, high-quality sellers should reach the top rather than simply being appended.

### 8. Preserve history

Before/after tests must prove preservation of:

- disposition
- notes
- attempts
- last touch
- stage
- outcome
- verification state
- priority

### 9. Deploy the real source

After the local repair passes tests:

- update the actual deployment source
- commit to the correct repository
- push the correct branch
- trigger/await deployment
- identify deployment revision
- verify live

If credentials/access are missing, stop at the precise blocker and report it. Do not fake success.

### 10. Live verification gate

Compare:

`SOURCE_COUNT`
`DIALER_COUNT`
`LIVE_COUNT`

Also compare dataset version/hash or another immutable marker.

Verify live categories, top-of-queue records, phone state, lead details, scripts, and duplicate counts.

The browser must visibly prove the repair.

### 11. Idempotency

Run the sync twice.

Second run must not create duplicate leads, duplicate phones, duplicate publication records, or history loss. Unexpected changes are a failure to fix.

### 12. Regression tests

Cover:

- phone normalization
- dedupe
- seller classification
- buyer classification
- distressed seller qualification
- distressed property non-seller
- script generation
- missing-evidence human review
- history preservation
- ranking
- idempotency
- export/deployment verification

Fixtures must include fresh verified seller, buyer, distressed non-seller, duplicate phone, bad phone, missing owner evidence, and previously contacted seller with disposition.

## Final report

Return exactly:

- actual deployment repo/branch/provider
- deployed revision
- source count
- dialer count
- live count
- imported/updated/deduped/rejected
- verified/bad phones
- seller/distressed seller/buyer/wholesaler/general/human-review counts
- duplicate count before/after
- scripts ready/human-review
- history preserved
- test results
- idempotency result
- live verification result
- exact files changed
- obsolete/superseded scripts
- exact deploy and verify commands
- remaining founder-only blockers
- next 5 actions

## Definition of done

The task is DONE only when:

`https://mbm-dialer.higgsfield.app/`

is serving the newest canonical verified dataset, seller categories are correct, distressed sellers are evidence-backed, scripts match the records, duplicates are clean, history is preserved, deployment revision is known, and live verification passes.

Do not stop at code looks good. Do not stop at tests pass. Do not stop at commit. Do not stop at push. Prove production.
