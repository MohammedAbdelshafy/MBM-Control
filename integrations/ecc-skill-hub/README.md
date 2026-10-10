# ecc-skill-hub — ECC skill-intake hub (audited cherry-picks → MBM-Control)

**VibeFounder power #9:** *"Deploy a 63-agent / 249-skill swarm from GitHub"*
([ECC Tools reel](https://www.instagram.com/reel/DZE2cgpONKp/)) →
**MBM-Control GLM workforce / Wholesaler Lead Engine / DataClean AI**.

The reel's premise — "10 months of someone else's agent engineering, free" —
is real: `affaan-m/ECC` on GitHub genuinely carries ~68 agent definitions
and ~293 skill directories (MIT licensed, actively updated). But the backing
claim ("63 agents / 249 skills / 180K stars") was **unverifiable from GitHub
search** at mapping time, and any bundle that auto-runs inside coding agents
is a supply-chain surface. The founder's standing directive for this power
was: **audit it, do not adopt it blindly**.

So this integration is not a blind vendor-in. It is the **intake hub**:
a safety auditor + a curated, pinned, re-scanned subset of 9 skills that map
onto the founder's products — each vendored at a fixed commit, each with a
named role, product mapping, activation slots, and a reviewer verdict.

## Layout

| File | What |
|---|---|
| `audit.py` | reusable safety + inventory auditor for any agent-skill repo (stdlib, read-only) |
| `library.py` | curated pick catalog: role, product mapping, `needs`, verdict |
| `picks/<skill>/` | vendored SKILL.md (+ bundled agents), pinned to commit `5cc14d7` |
| `mcp_server.py` | stdlib MCP stdio server (5 tools) |
| `test_smoke.py` | 18 hermetic tests — no network, no keys |
| `AUDIT.md` | the full audit findings (counts, pattern scan, verdict) |
| `PROVENANCE.txt` | source repo + pinned commit |
| `SKILL.md` | reusable skill doc |
| `WIRING.md` | where each pick plugs into the founder's products |
| `TEST_EVIDENCE.md` | test results |

## Quickstart

```bash
# 1. Audit any third-party agent-skill repo (read-only, hermetic):
python3 audit.py /path/to/cloned-repo
python3 audit.py /path/to/cloned-repo --json | jq '.inventory'

# 2. Look at the curated picks:
python3 - <<'EOF'
from library import PICKS
for p in PICKS:
    print(f"{p.slug:28} [{p.verdict:11}] → {p.product}")
EOF

# 3. Run the MCP server (stdio):
python3 mcp_server.py
```

## MCP tools

`skill_list` (the 9 vetted picks), `skill_get` (full SKILL.md + bundled
files), `skill_search` (keyword over slug/role/why/product),
`pick_install` (copy a pick into a target dir — dry-run by default,
refuses to overwrite), `audit_run` (run the auditor on any local repo).

Wire-up (Claude Code / Cursor):

```json
{"mcpServers": {"ecc-skill-hub": {
    "command": "python3",
    "args": ["<abs path>/mcp_server.py"]}}}
```

## The 9 picks (see WIRING.md for the product mapping)

| Pick | Serves | Role |
|---|---|---|
| `lead-intelligence` | Wholesaler Lead Engine / outreach | Agent-powered lead intel (Apollo/Clay replacement) |
| `cost-aware-llm-pipeline` | MBM-Control | LLM spend router — margin guard |
| `agent-eval` | MBM-Control | Head-to-head agent shootouts |
| `benchmark-optimization-loop` | MBM-Control | Measured "make it faster" loop |
| `eval-harness` | MBM-Control | Eval-driven agent development |
| `agent-architecture-audit` | MBM-Control | 12-layer agent-stack diagnostic |
| `marketing-campaign` | DataClean AI / AI Consultancy | Launch-campaign orchestration |
| `social-publisher` | outreach pipe | Agent-driven multi-platform publishing (needs `SC_API_KEY`) |
| `data-scraper-agent` | Wholesaler Lead Engine | Scheduled public-data collector (needs Gemini key + storage sink) |

## Honest limits

- The auditor is **heuristic, not a guarantee**: a clean scan means no
  known-bad patterns were found in prompt text, not that a skill is
  provably safe. Human review of flagged files is still the gate.
- 7 of 9 picks are pure prompt knowledge (no scripts, nothing executes).
  `social-publisher` and `data-scraper-agent` are **CONFIG-SLOT**: safe
  text, but activation needs credentials the founder must supply.
- The vendored copies are a **snapshot at commit `5cc14d7`** — they do
  not track ECC upstream. Re-audit before refreshing.
- ECC's own install scripts / hooks were **not** vendored and are not
  executed by this hub — that is deliberate (the supply-chain risk the
  audit was built to catch).
- Star counts cannot be independently verified from the GitHub API
  (search-side data, bots exist); the audit verified the *code*, not the
  *stars*.
