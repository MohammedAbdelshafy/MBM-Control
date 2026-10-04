# WhatsApp AI Front Desk — n8n + Meta Cloud API reference build

A fully-owned (no Kapso dependency) WhatsApp support agent on the n8n stack:
**WhatsApp Business Cloud API + n8n + OpenAI**. Reference implementation for the
AI Front Desk offer (WhatsApp intake → qualification → human escalation → follow-up).

## How the pieces fit

- `n8n_workflow.json` — the **production** workflow. Import into n8n:
  Webhook (Meta callbacks) → IF (verify challenge vs message event) →
  Set (extract sender/text) → OpenAI node (front-desk brain) →
  HTTP Request (POST reply to Graph API) → Respond 200.
- `front_desk_logic.py` — the qualification state machine as pure, importable
  Python: greet → name → service → urgency → done, with FAQ answers and
  escalation triggers. No network calls — reuse it anywhere (n8n Code node,
  your own server, tests).
- `webhook_harness.py` — **local dev/test server** (stdlib only) that emulates
  the Meta webhook contract exactly: GET verify (hub.mode/hub.verify_token/
  hub.challenge echo) and POST message callbacks. DRY_RUN=1 (default) writes
  the would-be Graph reply payload to stdout + `dry_run_outbox.jsonl` instead
  of sending anything.
- `test_harness.py` — runs the real tests: verification contract, inbound
  parsing, dry-run payload shape, and the full logic state-machine suite.

## Local test

```bash
cd ~/workspace/night-shift/whatsapp-n8n-frontdesk
cp .env.example .env   # fill VERIFY_TOKEN (any random string for local tests)
python3 test_harness.py
```

Or run the harness standalone and poke it manually:

```bash
VERIFY_TOKEN=mysecret DRY_RUN=1 python3 webhook_harness.py
curl "http://127.0.0.1:8765/webhook?hub.mode=subscribe&hub.verify_token=mysecret&hub.challenge=ping"
```

## Going live — Meta app setup checklist

1. Create an app at developers.facebook.com → add the **WhatsApp** product.
2. In WhatsApp → API Setup: note the **test phone number** and generate a
   **temporary access token** (later: a permanent system-user token).
3. Note the **Phone Number ID** from the same page.
4. Configure the webhook: callback URL = your public n8n webhook URL
   (`https://<n8n-host>/webhook/whatsapp-webhook`), verify token = your
   `VERIFY_TOKEN` (Meta will call GET with hub.mode=subscribe — the workflow
   answers it), subscribe to the **messages** field.
5. On the n8n host set env vars: `VERIFY_TOKEN`, `WHATSAPP_TOKEN`,
   `PHONE_NUMBER_ID`. Add the OpenAI credential to the Front Desk Brain node
   and the HTTP Header Auth credential (`Authorization: Bearer <WHATSAPP_TOKEN>`)
   to the Reply node.
6. Test from the Meta dashboard ("send message" to your own number), then
   activate the workflow.

For production traffic beyond the test number, complete Meta's business
verification and request messaging limits upgrades in the app dashboard.
