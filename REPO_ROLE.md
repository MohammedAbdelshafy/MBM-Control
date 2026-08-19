# Repository Role: MBM Core

This is the **canonical execution repository for MoneyBeast Machine (MBM)**.

## Owns

- MBM production application
- LeadEngine / lead sourcing and verification
- Dialer and lead-database synchronization
- GTM / revenue execution
- operational scripts and production tests
- Contec ERP implementation work once it becomes executable product code

## Does not own

- Cross-repo mission control and governance: use `MohammedAbdelshafy/jarvis-mbm`
- Social clipping / publishing engine: use `MohammedAbdelshafy/MBM-Social`
- Unrelated upstream/reference projects

## Canonical rule

When an MBM idea appears in another repo, do not duplicate the subsystem here and there. Decide which repository owns it, then keep a single implementation and link the other project to it.

## Source of truth

The cross-repository ownership map lives in [`jarvis-mbm/REPO_REGISTRY.md`](https://github.com/MohammedAbdelshafy/jarvis-mbm/blob/claude/antigravity-bridge/REPO_REGISTRY.md).

**Last registry audit:** 2026-08-19
