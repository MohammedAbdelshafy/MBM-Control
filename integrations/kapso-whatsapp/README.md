# Kapso WhatsApp — AI Front Desk reference implementation

**Power:** "Give an AI agent a WhatsApp number in 2 commands" (Kapso CLI).
**Target:** the AI Front Desk offer — WhatsApp intake → 4-question qualification → human escalation.

## The 2-command flow

```bash
npm install -g @kapso/cli   # command 1: install
kapso setup                 # command 2: interactive — links a Kapso account and provisions/links a WhatsApp number
```

Verified 2026-10-04: `@kapso/cli@0.19.0` is the latest on npm; `login`, `setup`, and `status` all exist exactly as advertised.

## What's automated vs founder-required

| Step | Who | How |
|------|-----|-----|
| Environment check (node/npm/CLI) | automated | `bin/kapso_doctor.sh` → exit 0 ready / exit 2 missing |
| Kapso login + WhatsApp number provisioning | **FOUNDER** | interactive `kapso login` + `kapso setup` — only the founder can do this |
| Number health + project link | founder (one command each) | `kapso whatsapp numbers health`, `kapso link` |
| Install the intake agent prompt | automated after setup | fill `front-desk/agent_prompt.md` facts, push via `kapso push` |
| Self-test from a personal phone | **FOUNDER** | message the number, trigger "human" escalation |
| Day-2 ops (review chats, send, templates) | automated | `kapso whatsapp conversations|messages|templates` |

## Files

- `bin/kapso_doctor.sh` — environment + session health check (exit 0/2)
- `KAPSO_CLI_REFERENCE.md` — real captured `--help` for every relevant command
- `front-desk/agent_prompt.md` — WhatsApp intake agent system prompt (SMB-tuned)
- `front-desk/escalation_rules.md` — 8 exact condition → handoff behaviors
- `front-desk/provision_checklist.md` — phase-by-phase go-live checklist
- `SKILL.md` — workspace skill for the main agent
- `TEST_EVIDENCE.md` — real test output

## Constraint honored

No invented subcommands, flags, or endpoints anywhere. Everything operational traces back to `KAPSO_CLI_REFERENCE.md`, captured from the actual package. WhatsApp provisioning is never faked — the doctor reports "not logged in / not set up" honestly until the founder runs `kapso setup`.
