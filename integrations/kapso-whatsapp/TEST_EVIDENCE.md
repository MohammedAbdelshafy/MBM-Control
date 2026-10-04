# Test Evidence — kapso-whatsapp night-shift build

Built and tested 2026-10-04 (UTC ~18:25). All output below is real, captured from the actual tools — nothing simulated.

## (a) `npm view @kapso/cli version`

```
$ npm view @kapso/cli version
0.19.0
$ npm view @kapso/cli dist-tags
{ latest: '0.19.0' }
```

## (b) `npx -y @kapso/cli@0.19.0 --help` (full output)

```
Kapso CLI for source-controlled workflows, functions, WhatsApp numbers, conversations, messages, and templates

VERSION
  @kapso/cli/0.19.0 linux-x64 node-v24.20.0

USAGE
  $ kapso [COMMAND]

TOPICS
  customers  Manage customers in the current project
  logs       Search Rails logs in the current project
  projects   Manage Kapso project context
  whatsapp   Operate WhatsApp numbers, webhooks, conversations, messages, and
             templates

COMMANDS
  build   Compile Kapso workflow.ts or workflow.js files into source JSON
  help    Display help for kapso.
  link    Bind this directory to a Kapso project for pull and push
  login   Log in to Kapso
  logout  Log out from Kapso
  pull    Pull Kapso functions and workflows into this repo
  push    Push local Kapso functions and workflows
  setup   Guided first-time setup for Kapso and a WhatsApp number
  status  Show Kapso setup and project status
```

Per-subcommand help (`setup`, `login`, `status`, `whatsapp`, `whatsapp numbers`, `whatsapp conversations`, `whatsapp messages`, `whatsapp templates`, `link`, `pull`, `push`, `customers`) was captured verbatim in `KAPSO_CLI_REFERENCE.md`.

## (c) `bin/kapso_doctor.sh` run on this machine

```
$ ./bin/kapso_doctor.sh
Kapso WhatsApp — environment doctor
Date: 2026-10-04T18:25:46Z

== 1. node / npm ==
  [OK]   node found: /usr/bin/node (v24.20.0)
  [OK]   npm found: /opt/hatch-image/bin/npm (10.9.4)

== 2. @kapso/cli resolution ==
  [OK]   CLI resolvable via: npx one-shot @kapso/cli@0.19.0 (not installed globally)

== 3. CLI version + advertised commands ==
  [OK]   kapso --version => @kapso/cli/0.19.0 linux-x64 node-v24.20.0
  [OK]   kapso --help returned output (24 lines)
  [OK]   --help advertises 'login' command
  [OK]   --help advertises 'setup' command
  [OK]   --help advertises 'status' command

== 4. login / project session state (read-only) ==
  [INFO] kapso status output (first 20 lines):
         {
           "data": {
             "authenticated": false,
             "authentication_mode": "none",
             "project_access": {
               "ready": false
             }
           },
           "next": [
             {
               "command": "kapso login"
             }
           ]
         }

RESULT: 8 checks passed, 0 failed
STATUS: READY FOR FOUNDER SETUP — environment is good.
Next (founder, interactive): npm install -g @kapso/cli && kapso setup

DOCTOR EXIT CODE: 0
```

**Honest state:** CLI is installable and all advertised commands exist, but `authenticated: false` — no Kapso account is logged in and no WhatsApp number is provisioned on this machine. That provisioning is genuinely interactive and un-fakeable; it awaits the founder.

## (d) Script validation

- `bash -n bin/kapso_doctor.sh` → `SYNTAX OK`
- `shellcheck` → not installed on this host (skipped; documented here rather than silently omitted)

## Files delivered

- `bin/kapso_doctor.sh`
- `KAPSO_CLI_REFERENCE.md`
- `front-desk/agent_prompt.md`
- `front-desk/escalation_rules.md`
- `front-desk/provision_checklist.md`
- `SKILL.md`
- `README.md`
- `TEST_EVIDENCE.md` (this file)

## Constraint audit

- No invented Kapso subcommands, flags, or endpoints. One near-miss during drafting (an invented `--push` flag line in the reference doc) was caught and removed before delivery.
- No faked WhatsApp provisioning: the doctor and this evidence report the real `authenticated: false` state.
- No TODOs or stubs; no credentials handled or stored anywhere.
