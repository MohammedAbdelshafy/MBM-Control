# Agent Operating Policy

## Authorization Levels

### L0: READ
- **Capabilities:** Can inspect code, read issues, view PRs, and query APIs.
- **Restrictions:** Cannot mutate state, propose changes, or execute external API calls.

### L1: PROPOSE (Default)
- **Capabilities:** Can generate code, create artifacts, and draft plans.
- **Restrictions:** Cannot commit code, deploy, or run state-mutating actions without explicit authorization.

### L2: REVIEW-GATED WRITE
- **Capabilities:** Can create commits and open PRs.
- **Requirements:** Requires explicit elevation. Commits must be reviewed.
- **Restrictions:** Cannot push directly to protected branches, deploy, or execute CRM writes.

### L3: EXPLICITLY AUTHORIZED AUTOMATION
- **Capabilities:** Trusted CI/CD automation capable of deployment, spending, or outbound messaging.
- **Restrictions:** Operates under strict bounds (e.g., specific workflows). No agent may silently self-elevate to this level.

## Explicit Elevation Requirements
Elevation beyond L1 requires explicit human authorization for:
- Git push operations
- Workflow modifications
- Production deployments
- CRM / Lead / Customer data mutation
- Paid provider invocations (spending)
- Outbound messaging (SMS, Email, Social Publishing)
