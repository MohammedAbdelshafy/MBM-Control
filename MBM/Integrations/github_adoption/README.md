# GitHub Intelligence Adoption Layer

This module captures the first application pass from the GitHub intelligence pipeline.
It does **not** install third-party code into production and does not replace the MBM
Event Bus or Jarvis control plane.

## Selected repositories

| Repository | Version | Decision | Target |
|---|---:|---|---|
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | 0.9.4 | adopt after sandbox | web/data ingestion |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | 0.0.82 | adopt after sandbox | browser/MCP worker |
| [Google ADK Python](https://github.com/google/adk-python) | 2.9.2 | secondary agent runtime | specialized workflows |
| [Trigger.dev](https://github.com/triggerdotdev/trigger.dev) | 4.6.4 | lab only | durable execution |

## Architecture boundary

```
Jarvis
  |
MBM Event Bus / Mission System
  |
  +--> browser adapter ------> Playwright MCP
  |
  +--> web ingestion --------> Crawl4AI
  |
  +--> specialist runtime --> Google ADK
  |
  +--> selected long jobs ---> Trigger.dev (optional)
```

Jarvis remains the decision authority. Third-party runtimes only execute scoped work
after the MBM mission layer grants permission.

## Evaluation rules

1. Pin dependency versions.
2. Test outside production.
3. No third-party code gets direct access to authoritative lead stores.
4. Web content is untrusted input.
5. Browser writes require approval.
6. Provider credentials stay behind dedicated adapters.
7. Any adoption must preserve the MBM single-writer invariant.

## Exact evaluation setup

### Crawl4AI

```bash
python -m venv .venv-crawl4ai
# activate the venv
python -m pip install --upgrade pip
python -m pip install crawl4ai==0.9.4
crawl4ai-setup
crawl4ai-doctor
```

For source-level evaluation:

```bash
git clone https://github.com/unclecode/crawl4ai.git
cd crawl4ai
git checkout v0.9.4
pip install -e ".[all]"
pytest
```

### Playwright MCP

```npx @playwright/mcp@0.0.82 --no-webmcp --file-paths=absolute```

Keep WebMCP disabled for the first evaluation because page-provided tool names,
schemas and results are untrusted.

### Google ADK

```bash
python -m pip install google-adk==2.9.2
```

Run the upstream evaluation suite before routing any MBM missions to ADK.

### Trigger.dev

Use a dedicated TypeScript evaluation project. Pin the SDK/CLI to **4.6.4**.
Test retry, queue, idempotency and checkpoint behavior before considering an adapter.

## Commercial / license notes

- Crawl4AI and Playwright MCP are Apache-2.0. Crawl4AI's project requests attribution.
- Google ADK Python is Apache-2.0.
- Trigger.dev is Apache-2.0.
- No repository code is copied into this adapter package. These integrations call the
  upstream projects as external dependencies/runtimes.

## Next promotion gates

- Crawl4AI: 20-site extraction benchmark + SSRF/DNS-rebinding network test.
- Playwright MCP: 20 read-only browser tasks + approval gate tests.
- ADK: 10 synthetic specialist-agent missions + state/error regression suite.
- Trigger.dev: 10 retry/idempotency/checkpoint scenarios.

Only a passing benchmark and explicit architecture review should promote an adapter
beyond the lab.
