# WIRING — where the 9 picks plug into the founder's products

"Rebrand" reading: each pick becomes a named MBM-Control capability served
through this hub's MCP server, not a silent third-party dependency.

## MBM-Control / GLM workforce (margin + reliability)

| Pick | Capability name | Unlocks |
|---|---|---|
| `cost-aware-llm-pipeline` | **Margin Router** | Model routing by task complexity, budget tracking, retry logic, prompt caching — stops the swarm burning paid credits on draft work. Pairs with power #7 (ollama-local): local drafts + routed frontier calls |
| `agent-eval` | **Agent Shootout** | Head-to-head coding-agent comparisons on pass rate / cost / time / consistency — extends the 2026-10-07 bench verdicts with a reusable harness |
| `benchmark-optimization-loop` | **Measured Speedup** | Baseline → one-hypothesis variants → correctness gate → promote fastest — disciplined optimization for swarm runners |
| `eval-harness` | **Reliability Gate** | Eval-driven development for agent tasks: define pass/fail before coding, grade with code/model/rule/human graders — the missing reliability layer for overnight builds |
| `agent-architecture-audit` | **Stack Doctor** | 12-layer diagnostic (wrapper regression, memory pollution, tool-discipline failures, hidden repair loops) with severity-ranked, code-first fixes — run before shipping any agent app |

## Wholesaler Lead Engine

| Pick | Capability name | Unlocks |
|---|---|---|
| `lead-intelligence` | **Lead Intel** | Agent-powered signal scoring, mutual ranking, warm-path discovery, source-derived voice modeling, channel-specific outreach drafts — the Apollo/Clay/ZoomInfo replacement the engine's seller-finding needs. Bundled sub-agents: enrichment-agent, mutual-mapper, outreach-drafter, signal-scorer |
| `data-scraper-agent` | **Intel Feed** | Scheduled public-data collectors (job boards, prices, news, GitHub), AI-enriched, stored to Notion/Sheets/Supabase. Activation: Gemini key (founder's gemini connector is live) + a storage sink of choice |

## DataClean AI / AI Consultancy Sprint (the $499 / $297 pitches)

| Pick | Capability name | Unlocks |
|---|---|---|
| `marketing-campaign` | **Launch Orchestrator** | Audience research, positioning, landing copy, email sequences, social posts, ad copy, short-form video scripts, content calendars — the execution layer behind the pitches. Works with power #8 (bolt-slides): campaigns need decks, decks need campaigns |

## Outreach pipe

| Pick | Capability name | Unlocks |
|---|---|---|
| `social-publisher` | **Publish Bot** | Agent-driven scheduling/publishing across 13 platforms via one workspace API. Publishing is automated; outreach itself stays manual per the founder's warm-outreach guardrails. Activation: `SC_API_KEY` from a SocialClaw account — founder decision |

## What does NOT wire in yet

- The other 284 ECC skills: unreviewed by design. New intake = clone at a
  pinned commit → `audit_run` → review HIGH/MEDIUM → vendoring + catalog
  entry here.
- Anything needing ECC's own `install.sh`/hooks: deliberately excluded.
