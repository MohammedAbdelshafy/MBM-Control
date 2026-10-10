# Skill: ecc-skill-hub

Audited intake for third-party agent skills — built from VibeFounder power #9
("deploy a 63-agent / 249-skill swarm from GitHub", the ECC reel).

## When to use

- Before adopting any third-party agent skill/agent/hook bundle: run
  `python3 audit.py /path/to/clone` (or the `audit_run` MCP tool) and read
  the HIGH/MEDIUM findings with their excerpts. The scanner is heuristic —
  flagged warning-text is a false positive with a good sign attached; flagged
  payloads are a stop sign.
- When MBM-Control needs a capability the GLM workforce doesn't have yet:
  `skill_search` the 9 vetted picks first (lead intel, cost routing, agent
  evals, benchmarks, eval harness, architecture audit, campaign planning,
  social publishing, data scraping), then `pick_install` (dry-run default)
  to copy a pick into a repo. Copies never touch the network and refuse to
  overwrite.
- Never `install.sh` a skill bundle into a founder machine. Install picks
  from this hub instead.

## The 9 vetted picks

| Slug | Product | Role | Activation |
|---|---|---|---|
| lead-intelligence | Wholesaler Lead Engine / outreach | Agent-powered lead intel (Apollo/Clay replacement) | WebSearch-capable runtime |
| cost-aware-llm-pipeline | MBM-Control | LLM spend router — margin guard | none |
| agent-eval | MBM-Control | Head-to-head agent shootouts | none |
| benchmark-optimization-loop | MBM-Control | Measured "make it faster" loop | none |
| eval-harness | MBM-Control | Eval-driven agent development | none |
| agent-architecture-audit | MBM-Control | 12-layer agent-stack diagnostic | none |
| marketing-campaign | DataClean AI / AI Consultancy | Launch-campaign orchestration | none |
| social-publisher | outreach pipe | Agent-driven multi-platform publishing | needs `SC_API_KEY` (SocialClaw) |
| data-scraper-agent | Wholesaler Lead Engine | Scheduled public-data collector | needs Gemini key + storage sink |

## MCP tools

`skill_list`, `skill_get`, `skill_search`, `pick_install`, `audit_run`.

Wire-up:

```json
{"mcpServers": {"ecc-skill-hub": {
    "command": "python3",
    "args": ["<abs path>/mcp_server.py"]}}}
```

## Provenance

Vendored from https://github.com/affaan-m/ECC at commit
`5cc14d7c3155c7dcd4059c94b89df4b6303b7cd6` (MIT). Full audit in AUDIT.md.
