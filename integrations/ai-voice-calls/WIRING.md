# WIRING — ai-voice-calls → founder products

How this power plugs into the stack. All paths assume the same MCP server;
only the assistant config and lead source change per product.

## 1. Wholesaler Lead Engine — AI-voice lead follow-up (outbound)

**Lane:** "Your sellers get a call within minutes, from an AI that qualifies."

- Lead source: the 100-record call-now CSV (`number,name[, ...]`). Feed it
  through `load_leads_csv` / `voice_campaign_run(leads_csv=...)`.
- Campaign pattern per night-shift build: `voice_campaign_run` in dry-run,
  then `voice_cost_estimate(num_calls, avg_minutes)`; live on approval.
- Assistant config: system prompt = cash-buyer qualification script
  (confirm ownership, motivation, timeline, price expectation, appointment
  hand-off). `firstMessage` MUST disclose AI identity, e.g.:
  "Hi {name}, I'm an AI assistant calling on behalf of our home-buying team…"
- Outcome log (JSONL) feeds back into the intake sheet: call_id, status,
  per-lead notes → the human caller queue for hot leads.
- Pricing input: 100 calls × 2.5 min ≈ 300 billable min → ~$15 platform /
  $21–75 all-in (2026 estimates). Price the pilot accordingly.

**Compliance hard gates (enforced in code, not optional):**
- Consent column: only rows with `consent=true` are dialed.
- DNC: keep `dnc.csv` (manual opt-outs + FTC DNC where applicable) and pass
  it to every campaign run — suppressed numbers never dial.
- AI disclosure in the first message (`ensure_ai_disclosure`, waiver needs
  human sign-off).

## 2. AI Front Desk — voice receptionist (inbound-ready)

**Lane:** "AI Front Desk, now on voice."

- The Vapi adapter's `create_assistant` builds the receptionist config:
  greeting + booking/appointment intents, escalation to the human on
  uncertainty. Same disclosure rule applies to inbound.
- Outbound reminders (appointment confirmations, no-show recovery) run
  through the same campaign layer with a reminder assistant.
- Inbound number attach happens in the Vapi dashboard (provision a Vapi
  number → attach assistant). This repo holds the config and the compliance
  gates; provisioning itself is dashboard work, logged here.

## 3. MBM-Control swarm — monitoring hook

- `voice_call_list` + `voice_call_status` give the GLM workforce read access
  to call outcomes for the reporting digest: calls today, connect rate,
  qualified leads.
- Campaign JSONL logs are machine-readable: point the digest job at the
  log path.

## What is NOT built here (deliberately)

- Giga enterprise integration — no public self-serve API verified; keep as
  the per-client enterprise path if a client already has Giga.
- Auto-dialer at scale without consent — the compliance gates are the
  product; a "spam cannon" mode is a non-goal.
- Transcription/sentiment analysis of call recordings — the Vapi dashboard
  returns recordings/transcripts; wire `voice_call_status` → recording_url
  into the digest when a pilot is live.
