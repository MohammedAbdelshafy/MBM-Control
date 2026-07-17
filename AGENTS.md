# AGENTS.md — MBM Control Plane

## Project Context

This is the **Contech AI Agentic teamz** monorepo. It contains:
- **Frontend App** (`src/`) — React/Vite dashboard
- **Clipping Factory** (`clipping-factory/`) — Python/FastAPI video pipeline
- **MBM Social** (`clipping-factory/MBM-Social/`) — Brand management & publishing
- **MBM Ops** (`MBM/`) — Lead-gen, outreach, real estate scripts

## Workflow Rules

| Phase | Mode | What You Do |
|---|---|---|
| **plan** | read-only | Inspect, diagnose, propose. NO file edits. |
| **build** | full | Implement approved changes. One scope at a time. |
| **verify** | read-only | Test, lint, review. NO additional edits. Report issues. |

Default mode: **plan**. Explicitly switch with `/opencode build` or `/opencode verify`.

## Key Boundaries

- **Base44**: See `base44/` config. Use `base44 dev` for local backend. See [Base44 docs](https://docs.base44.com/developers/references/cli/get-started/overview.md).
- **Clipping Factory**: See `clipping-factory/CLIPPING.md` for pipeline, agents, and Docker stack.
- **MBM Social**: See `clipping-factory/MBM-Social/SOCIAL.md` for brand config, publishing, analytics.
- **MBM Ops**: See `MBM/MBM.md` for lead-gen, scripts, outreach, real estate.
- **Run checks**: `npm run lint && npm run typecheck && npm run build` before closing any build task.

## Quick Reference

```bash
npm run dev              # Frontend dev server
npm run clip:build       # Build one clip end-to-end
npm run clip:server      # Start FastAPI + Celery workers (docker compose up)
npm run hunt:send        # Send outreach emails
```

## CI Pipeline

`.github/workflows/`:
- `check.yml` — lint/typecheck/build on push/PR
- `schedule.yml` — hourly: email queue, lead pipeline, clipping scan
- `health-report.yml` — nightly: workflow YAML, env coverage, README freshness
- `mbm-social.yml` — brand validation on MBM-Social changes

## Output Contract

Every workflow emits:
```
status: success | failure | skipped
inputs: { ... }
outputs: { ... }
errors: [ ... ]
next_action: string
owner: "system" | "human"
timestamp: ISO8601
```
