---
name: kapso-whatsapp
description: Provision and operate an AI agent on WhatsApp via the Kapso CLI — the reference channel implementation for the AI Front Desk offer (WhatsApp intake → qualification → human escalation). Triggers: AI Front Desk, WhatsApp agent setup, Kapso.
---

# kapso-whatsapp

## Purpose

Turn a founder's WhatsApp number into an AI front desk: greeting, 4-question qualification, FAQ answers, and rule-based escalation to a human. Everything up to the account/phone provisioning is scripted; the interactive account steps stay with the founder.

## Tooling

All files live in `~/workspace/night-shift/kapso-whatsapp/`:

- `bin/kapso_doctor.sh` — environment check. Run first. Exit 0 = ready, exit 2 = missing prerequisites.
- `KAPSO_CLI_REFERENCE.md` — the real `--help` output captured from `@kapso/cli@0.19.0`. **The only source of truth for commands.** Never invent subcommands, flags, or API endpoints.
- `front-desk/agent_prompt.md` — the intake agent's system prompt (fill in bracketed business facts).
- `front-desk/escalation_rules.md` — 8 exact condition → handoff behaviors.
- `front-desk/provision_checklist.md` — end-to-end go-live checklist.

Verified real commands (0.19.0): `kapso login`, `kapso setup`, `kapso status`, `kapso link`, `kapso pull`, `kapso push`, `kapso whatsapp numbers|conversations|messages|templates`, `kapso customers`, `kapso projects`.

## Auth

- The Kapso account and WhatsApp number belong to the founder. Login happens via the interactive `kapso setup` / `kapso login` — **the agent never handles credentials, browser logins, or OTPs.**
- The agent works only with `kapso status` (read-only) and post-setup project commands.

## Operating Rules

1. Never invent a Kapso subcommand or flag. If it's not in `KAPSO_CLI_REFERENCE.md`, run `kapso <cmd> --help` first.
2. The `kapso setup` step requires the founder (interactive provisioning). Queue it as an explicit human action; do not fake it.
3. The agent prompt must have every bracketed fact filled before go-live — the agent may never improvise prices, hours, or availability.
4. `kapso whatsapp numbers health` must read healthy before declaring go-live.
5. Report honestly: "CLI installable, not logged in" is a valid, final state until the founder acts.
