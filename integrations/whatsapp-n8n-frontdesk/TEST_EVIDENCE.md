# TEST EVIDENCE — WhatsApp n8n Front Desk

All output below is real, captured 2026-10-04. No real Graph API calls were
made; everything ran locally in dry-run mode.

## (a) py_compile — all Python files

```
$ python3 -W error -m py_compile front_desk_logic.py webhook_harness.py test_harness.py
py_compile: OK, no warnings (3 files)
```

## (b) n8n_workflow.json structure validation

```
$ python3 -c "import json; wf = json.load(open('n8n_workflow.json')); ..."
workflow name: WhatsApp AI Front Desk
node count: 8
 - WhatsApp Webhook | n8n-nodes-base.webhook
 - Is Verify Challenge? | n8n-nodes-base.if
 - Echo Challenge | n8n-nodes-base.respondToWebhook
 - Extract Sender + Text | n8n-nodes-base.set
 - Front Desk Brain | n8n-nodes-base.openAi
 - Reply via WhatsApp | n8n-nodes-base.httpRequest
 - Ack 200 | n8n-nodes-base.respondToWebhook
 - Notes | n8n-nodes-base.stickyNote
connections: 5
```

Required top-level keys present: `name`, `nodes`, `connections`. All node
types used are certain to exist in n8n (webhook, if, httpRequest, set, openAi,
respondToWebhook, stickyNote) — no WhatsApp-specific node assumed.

## (c) Full test_harness.py run — 28/28 passing

```
$ python3 test_harness.py
== (a) webhook verification contract ==
PASS: verify GET with correct token echoes challenge
PASS: verify GET with wrong token returns 403
== (b) inbound message parsing + dry-run reply ==
PASS: POST inbound returns 200 ok
PASS: sender parsed
PASS: stage is qualify_name after first message
PASS: reply asks for name
PASS: not escalated
PASS: dry-run flag set
PASS: reply payload has whatsapp product
PASS: reply payload targets sender
PASS: reply payload carries reply text
PASS: turn 'Omar' -> stage qualify_service
PASS: turn 'I need cleaning' -> stage qualify_urgency
PASS: turn 'today please' -> stage done
PASS: escalation keyword escalates
== (c) front_desk_logic unit tests ==
PASS: greet -> qualify_name
PASS: name captured, -> qualify_service
PASS: FAQ price answer inline, stage unchanged
PASS: service captured, -> qualify_urgency
PASS: urgency captured, -> done
PASS: done stays done, offers human
PASS: escalation trigger 'I want a human'
PASS: escalation trigger 'agent please'
PASS: escalation trigger 'call me tomorrow'
PASS: escalation trigger 'get me a real person'
PASS: first failed parse asks again
PASS: second failed parse escalates
PASS: empty message handled gracefully

28 passed, 0 failed
ALL TESTS PASSED
```

## (d) Sample dry-run reply payload

Inbound: `hi` from `15551234567`. The harness ran the state machine and
wrote the would-be Graph API payload (dry-run, nothing sent):

```json
{
  "stage": "qualify_name",
  "escalate": false,
  "reply": "Hello! Thanks for reaching out. I'm the front desk assistant. What's your name?",
  "graph_payload": {
    "messaging_product": "whatsapp",
    "to": "15551234567",
    "type": "text",
    "text": {
      "body": "Hello! Thanks for reaching out. I'm the front desk assistant. What's your name?"
    }
  }
}
```

## Notes

- The Graph API POST code path (`send_or_dry_run` live branch) exists but is
  guarded by `DRY_RUN=0` + real `WHATSAPP_TOKEN` + `PHONE_NUMBER_ID` and was
  never executed — no credentials exist in this build.
- Webhook verification implements only the documented Meta contract:
  `hub.mode=subscribe` + `hub.verify_token` match → echo `hub.challenge`;
  otherwise 403.
