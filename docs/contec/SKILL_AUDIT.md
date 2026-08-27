# Contec ERP Skill Audit

**Date:** 2026-08-26
**Auditor:** OX ALPHA

## 1. Existing Capabilities

### Local Project Skills (`.agents/skills/`)
An extensive set of 66 skills exists in the current environment. 
Relevant existing skills that should be **reused** for Contec ERP:
- `qa`: General quality assurance and deliverable auditing.
- `evidence-collector`: Web/system evidence scraping and validation.
- `mission-planner`: Workflow breakdown and checklist creation.

Non-relevant skills primarily focus on external domains (e.g., `real-estate-underwriting`, `salesforce-crm-copilot`, `higgsfield-*`) and OmniRoute management (`omni-*`, `cli-*`).

### MCP Configurations (`.agents/mcp_config.json`)
The following MCP servers are configured:
- `clipping-factory`
- `supabase`
- `whop`
- `filesystem`
- `github`
- `sequential-thinking`

**Assessment:**
- `filesystem` and `github` are extremely valuable for code reading, commits, and recovery.
- `sequential-thinking` helps with architectural decisions.
- Database access is NOT configured as a direct write tool via MCP, adhering to the requirement to avoid unrestricted production write access.

### Global Configurations
- `AGENTS.md` and `.agents/AGENTS.md` contain strict rules on AI data hallucination, single-writer invariants, and zero-trust policies, aligning perfectly with Contec's goals.

## 2. Missing Capabilities

The environment lacks specific accounting and ERP engineering instructions. The following 12 core skills must be created locally for Contec:

1. `erpnext-frappe-expert`
2. `accounting-integrity`
3. `contec-trust-engine`
4. `receipt-intelligence`
5. `arabic-rtl-accounting`
6. `construction-finance`
7. `high-volume-data-entry`
8. `security-zero-trust`
9. `backup-disaster-recovery`
10. `deployment-devops`
11. `git-recovery-and-hygiene`
12. `qa-release-gate`

## 3. Specialist Agents

To ensure the principle of least privilege, the following agents will be defined:
- **OX ALPHA**: Chief orchestrator
- **CONTEC ACCOUNTANT**: Uses `accounting-integrity` + `erpnext-frappe-expert`
- **CONTEC RECEIPT AGENT**: Uses `receipt-intelligence` + `arabic-rtl-accounting` + `contec-trust-engine`
- **CONTEC QA**: Uses `qa-release-gate` + `security-zero-trust`
- **CONTEC DEVOPS**: Uses `deployment-devops` + `backup-disaster-recovery` + `git-recovery-and-hygiene`
- **FRAPPE EXPERT**: Uses `erpnext-frappe-expert`

## 4. Risks & Next Steps
**Risk**: AI modifying core Frappe files.
**Mitigation**: Handled by `erpnext-frappe-expert` rules.

**Risk**: AI hallucinating financial data.
**Mitigation**: Mitigated via `accounting-integrity` and `contec-trust-engine`.

**Next Step**: Create the 12 missing `SKILL.md` files in `.agents/skills/`.
