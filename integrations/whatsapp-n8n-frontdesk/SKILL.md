---
name: whatsapp-n8n-frontdesk
description: Deploy and test a WhatsApp AI front-desk agent — Meta webhook contract, importable n8n workflow (webhook → OpenAI → Graph API reply), and a pure-Python qualification state machine. Use when wiring WhatsApp intake → qualification → human escalation → follow-up.
---

# WhatsApp n8n Front Desk

## Purpose

Reference implementation of the AI Front Desk offer on the fully-owned n8n
stack (no Kapso): WhatsApp Business Cloud API callbacks hit an n8n webhook,
an OpenAI node runs the front-desk brain, and an HTTP Request node posts the
reply back through the Graph API. Local dev/test is covered by a stdlib-only
harness that emulates the Meta webhook contract.

Working directory: `~/workspace/night-shift/whatsapp-n8n-frontdesk/`

## Tooling

**Local harness (dev/test, stdlib only):**

```bash
cd ~/workspace/night-shift/whatsapp-n8n-frontdesk
VERIFY_TOKEN=<any-string> DRY_RUN=1 python3 webhook_harness.py
python3 test_harness.py   # full suite: verification contract, inbound parsing, logic units
```

**n8n import steps (exact):**

1. n8n → Workflows → ⋯ → **Import from File** → select `n8n_workflow.json`.
2. Open the **Front Desk Brain** node → Credentials → create/select your
   OpenAI credential.
3. Open the **Reply via WhatsApp** node → Authentication: Generic Credential
   Type → HTTP Header Auth → `Authorization: Bearer <WHATSAPP_TOKEN>`.
4. On the n8n host, export env vars `VERIFY_TOKEN` and `PHONE_NUMBER_ID`
   (referenced as `{{ $env.VERIFY_TOKEN }}` / `{{ $env.PHONE_NUMBER_ID }}`).
5. **Test** the workflow (Test workflow button) — Meta's dashboard verify call
   and test message will execute the full path.
6. **Activate** the workflow only after a successful end-to-end test message.

**Conversation logic (reuse in n8n Code nodes or your own server):**

```python
from front_desk_logic import new_session, process_message
state = new_session(sender)
state, reply, escalate, stage = process_message(state, inbound_text)
```

Stages: `greet → qualify_name → qualify_service → qualify_urgency → done`,
with `escalate` reachable at any point (keywords: human, agent, call me, phone,
live person, or 2 failed service parses).

## Auth

Meta app tokens live in `.env` (see `.env.example`: `VERIFY_TOKEN`,
`WHATSAPP_TOKEN`, `PHONE_NUMBER_ID`, `OPENAI_API_KEY`) — **never in code or
in the workflow JSON**. The workflow reads tokens from env/credentials only.

## Operating Rules

1. **Dry-run is the default.** `DRY_RUN=1` writes would-be Graph API payloads
   to stdout + `dry_run_outbox.jsonl`; nothing is ever sent without real tokens
   *and* `DRY_RUN=0`.
2. **Never send real messages from tests.** `test_harness.py` runs fully
   offline on localhost; the Graph API code path is present but guarded and is
   never exercised by tests.
3. **Never invent Meta API behaviour.** The only contract emulated is the
   documented one: GET `hub.mode=subscribe&hub.verify_token&hub.challenge`
   verification (echo challenge on match, 403 otherwise) and POST
   `entry[].changes[].value.messages[]` message callbacks.
4. Token rotation: regenerate the WhatsApp token in the Meta dashboard and
   update the n8n credential + `.env`; the old token stops working immediately.
