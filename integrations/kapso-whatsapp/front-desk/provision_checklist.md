# AI Front Desk — Provision Checklist (Kapso)

**Goal:** a working WhatsApp number with the AI front-desk agent answering, tested end-to-end.
Steps marked **[FOUNDER]** require the founder (or the client) — they involve accounts, phone numbers, and interactive logins the agent cannot do.

## Phase 1 — Environment (automatable)

- [ ] Run `bin/kapso_doctor.sh` from this directory — exit 0 required.
- [ ] `npm install -g @kapso/cli` (or use the npx fallback the doctor resolves).

## Phase 2 — Kapso account + WhatsApp number **[FOUNDER]**

- [ ] **[FOUNDER]** Run `kapso login` — interactive; authenticates the founder's Kapso account.
- [ ] **[FOUNDER]** Run `kapso setup` — guided first-time setup. This provisions or links the WhatsApp number.
  - Useful non-interactive flags (all real, from `kapso setup --help`): `--country <ISO>`, `--area-code <code>`, `--connection-type dedicated|coexistence`, `--no-provision-phone-number` (link an existing number instead of provisioning a new one).
  - Keep the default `dedicated` connection type unless the number must coexist with the WhatsApp Business app.
- [ ] **[FOUNDER]** Confirm the number: `kapso whatsapp numbers list`, then `kapso whatsapp numbers health` on it — healthy required before go-live.
- [ ] **[FOUNDER]** If deploying into a repo: `kapso link` to bind the working directory to the Kapso project.

## Phase 3 — Install the front-desk agent (automatable once Phase 2 is done)

- [ ] Copy `front-desk/agent_prompt.md` into the Kapso project's agent/workflow configuration and fill in ALL bracketed business facts. The agent must never improvise prices, hours, or availability.
- [ ] Encode `front-desk/escalation_rules.md` as the handoff behavior (rule codes #1–#8).
- [ ] If the project uses source-controlled workflows: `kapso build`, review, then `kapso push --dry-run` first, then `kapso push`.

## Phase 4 — Test with your own phone **[FOUNDER]**

- [ ] **[FOUNDER]** Message the WhatsApp number from a personal phone. Confirm:
  - Greeting arrives and sounds like the business.
  - The 4 qualification questions are asked one at a time.
  - An FAQ (hours/price/location) is answered from the filled-in facts.
  - Typing "human" / "call me" triggers the escalation reply and the thread is released.
- [ ] **[FOUNDER]** Review the conversation in the CLI: `kapso whatsapp conversations list`, `kapso whatsapp messages list`.
- [ ] Fix prompt facts / escalation wording, re-push, re-test.

## Phase 5 — Go-live criteria

- [ ] `kapso whatsapp numbers health` = healthy.
- [ ] All 4 Phase-4 tests pass.
- [ ] Owner knows the escalation SLA and has the number saved for handoffs.
- [ ] `kapso status` shows the project linked and logged in.

## What the agent can do after go-live (real commands only)

- `kapso status --output json` — login/project state
- `kapso whatsapp numbers list|get|health` — number state
- `kapso whatsapp conversations list|get` — review chats
- `kapso whatsapp messages list|send` — review / send
- `kapso whatsapp templates list|get|new` — approved templates
- `kapso pull|push` — sync agent workflows from source control

Anything else: check `KAPSO_CLI_REFERENCE.md` or run `kapso <cmd> --help`. Never invent a subcommand.
