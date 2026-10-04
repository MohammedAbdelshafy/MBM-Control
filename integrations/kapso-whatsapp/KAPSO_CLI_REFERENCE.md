# Kapso CLI Reference — captured from the real package

**Package:** `@kapso/cli` — **captured version:** 0.19.0 (verified via `npm view @kapso/cli version`, 2026-10-04)
**Source:** `npx -y @kapso/cli@0.19.0 --help` and `kapso <cmd> --help` on a Linux x64 host, Node v24.20.0.
**Rule:** only the commands/flags shown below exist. Do not invent subcommands, flags, or API endpoints.

---

## `kapso --help` (top level)

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

## `kapso setup --help`

```
Guided first-time setup for Kapso and a WhatsApp number

USAGE
  $ kapso setup [--area-code <value>] [--connection-type
    coexistence|dedicated...] [--country <value>...] [--customer <value>]
    [--failure-url <value>] [--language <value>] [--no-provision-phone-number]
    [--output json|human] [--project <value>] [--success-url <value>]

FLAGS
  --area-code=<value>            Preferred phone number area code
  --connection-type=<option>...  Allowed connection type (defaults to dedicated)
                                 <options: coexistence|dedicated>
  --country=<value>...           Preferred phone number country ISO
  --customer=<value>             Customer ID override
  --failure-url=<value>          Failure redirect URL
  --language=<value>             Setup link language
  --no-provision-phone-number    Do not auto-provision a phone number during
                                 setup
  --success-url=<value>          Success redirect URL
  --project=<value>              Project ID override
  --output=<option>              [default: human] Output format
                                 <options: json|human>

DESCRIPTION
  Guided first-time setup for Kapso and a WhatsApp number
```

## `kapso login --help`

```
Log in to Kapso

USAGE
  $ kapso login

DESCRIPTION
  Log in to Kapso

EXAMPLES
  $ kapso login
```

## `kapso status --help`

```
Show Kapso setup and project status

USAGE
  $ kapso status [--output json|human]

FLAGS
  --output=<option>  [default: human] Output format
                     <options: json|human>

DESCRIPTION
  Show Kapso setup and project status
```

## `kapso whatsapp --help`

```
Operate WhatsApp numbers, webhooks, conversations, messages, and templates

USAGE
  $ kapso whatsapp COMMAND

TOPICS
  whatsapp conversations     Manage WhatsApp conversations
  whatsapp numbers           Manage WhatsApp numbers
  whatsapp project-webhooks  Manage project WhatsApp webhooks, including account
                             enforcement events
  whatsapp threads           Take, pass, or release WhatsApp conversation
                             control
  whatsapp webhooks          Manage WhatsApp webhooks for a number
  whatsapp messages          Manage WhatsApp messages
  whatsapp templates         Manage WhatsApp templates
```

## `kapso whatsapp numbers --help`

```
Manage WhatsApp numbers

USAGE
  $ kapso whatsapp numbers COMMAND

COMMANDS
  whatsapp numbers get      Get a WhatsApp number by Meta ID or display phone
                            number
  whatsapp numbers health   Run a health check for a WhatsApp number
  whatsapp numbers list     List WhatsApp numbers in the current project
  whatsapp numbers resolve  Resolve a WhatsApp number reference to a canonical
                            phone number ID
  whatsapp numbers new      Start WhatsApp number setup in the current project
```

## `kapso whatsapp conversations --help`

```
Manage WhatsApp conversations

USAGE
  $ kapso whatsapp conversations COMMAND

COMMANDS
  whatsapp conversations get   Get a WhatsApp conversation by ID
  whatsapp conversations list  List WhatsApp conversations in the current
                               project, sorted by most recent activity
```

## `kapso whatsapp messages --help`

```
Manage WhatsApp messages

USAGE
  $ kapso whatsapp messages COMMAND

COMMANDS
  whatsapp messages get   Get a WhatsApp message by ID
  whatsapp messages list  List WhatsApp messages in the current project (cursor
                          pagination)
  whatsapp messages send  Send a WhatsApp message
```

## `kapso whatsapp templates --help`

```
Manage WhatsApp templates

USAGE
  $ kapso whatsapp COMMAND

COMMANDS
  whatsapp templates get   Get a WhatsApp template by ID
  whatsapp templates list  List WhatsApp templates for a number (cursor
                           pagination)
  whatsapp templates new   Create a WhatsApp template for a number
```

## `kapso link --help`

```
Bind this directory to a Kapso project for pull and push

USAGE
  $ kapso link [--project <value>] [--verify]

FLAGS
  --project=<value>  Project ID override
  --[no-]verify      Verify Platform API access before writing the binding

DESCRIPTION
  Bind this directory to a Kapso project for pull and push
```

## `kapso pull --help`

```
Pull Kapso functions and workflows into this repo

USAGE
  $ kapso pull [KIND] [SLUG] [--diff] [--overwrite] [--project
    <value>]

ARGUMENTS
  [KIND]  (function|workflow) Optional source kind to pull
  [SLUG]  Function or workflow slug to pull

FLAGS
  --diff             Show incoming diffs for blocked local edits without writing
                     files
  --overwrite        Overwrite local files that changed since the last pull
  --project=<value>  Project ID override

DESCRIPTION
  Pull Kapso functions and workflows into this repo
```

## `kapso push --help`

```
Push local Kapso functions and workflows

USAGE
  $ kapso push [KIND] [SLUG] [--dry-run] [--project <value>]

ARGUMENTS
  [KIND]  (function|workflow) Optional source kind to push
  [SLUG]  Function or workflow slug to push

FLAGS
  --dry-run          Show the push plan without changing remote resources
  --project=<value>  Project ID override

DESCRIPTION
  Push local Kapso functions and workflows
```

## `kapso customers --help`

```
Manage customers in the current project

USAGE
  $ kapso customers COMMAND

COMMANDS
  customers get   Get a customer by ID
  customers list  List customers in the current project
  customers new   Create a customer in the current project
```

---

## Operator notes (Front Desk relevance)

- The advertised "2-command flow" maps to `kapso login` (authenticate) and `kapso setup` (guided first-time setup incl. WhatsApp number). Both are real, both exist at 0.19.0.
- `kapso status` is the read-only way to check login/project state — use `--output json` for machine parsing.
- Day-2 operations use only real topics: `kapso whatsapp numbers list|get|health`, `kapso whatsapp conversations list|get`, `kapso whatsapp messages list|send`, `kapso whatsapp templates list`.
- Agent logic (prompts, workflows) lives in source-controlled files pulled/pushed with `kapso pull|push` — the `front-desk/agent_prompt.md` in this bundle is the reference copy to adapt into the project's workflow after setup.
