---
type: repository
status: active
owner_repo: MohammedAbdelshafy/MBM-Control
product_name: Sales & Calling Workspace
source_of_truth: https://github.com/MohammedAbdelshafy/MBM-Control
---

# Sales & Calling Workspace CONTEXT

One job: help a salesperson work the next eligible lead, record the outcome and keep the next action visible.

## Inputs
- App setup: [README](README.md)
- Operating rules: [AGENTS](AGENTS.md)
- Product boundaries: [REPO_ROLE](REPO_ROLE.md), [MONETIZATION](MONETIZATION.md), [PRODUCT_REGISTRY](PRODUCT_REGISTRY.md)

## Process
1. Check the current lead queue, its source and its eligibility/suppression state.
2. Show call context and relevant approved talking points.
3. Record the result using the existing disposition schema.
4. Create or update the next follow-up through the canonical path.
5. Expose errors and exceptions instead of silently skipping a record.
6. Require human approval for external outreach and irreversible customer actions.

## Outputs
A clear prioritized queue, call notes/dispositions, follow-up actions and an auditable history.

## Check
No protected lead database writes outside its authorized writer; no call is initiated without verified provider configuration and required human approval. Treat product status and pricing in the registry as repository claims until runtime and payment paths are rechecked.
