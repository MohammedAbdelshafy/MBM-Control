# MBM Dialer Provider Architecture

MBM uses a provider boundary for outbound calling. **Phound is the preferred human calling provider** because it supplies the US number and unlimited calling entitlement used by the operator.

## Security model

- The browser never receives Phound API tokens.
- Do not scrape, reverse-engineer, or replay private Phound app traffic.
- No undocumented Phound endpoint is assumed by the adapter.
- When Phound Business/API access is provisioned, set the official endpoint and token in server-side environment variables.
- The adapter normalizes outbound numbers to E.164 and applies request timeouts.
- API responses are reduced to a bounded JSON payload and provider errors do not expose secrets.

## Provider modes

### Native app mode

Default. The MBM website prepares the lead, script, notes, and call context. The operator places the call in Phound using the configured US number.

### API mode

Enable only after Phound provides/approves the integration endpoint for the account.

```env
PHOUND_ENABLED=true
PHOUND_CALL_ENDPOINT=https://YOUR-OFFICIAL-PHOUND-ENDPOINT
PHOUND_API_TOKEN=YOUR_SERVER_SIDE_TOKEN
PHOUND_TIMEOUT_MS=8000
PHOUND_AUTH_HEADER=Authorization
```

The payload sent by the adapter is intentionally small and normalized:

```json
{
  "to": "+12125551234",
  "prospect_name": "Prospect",
  "lead_id": "lead-id",
  "notes": "Optional call context"
}
```

The exact endpoint, authentication scheme, and payload mapping must come from the official Phound integration documentation/account configuration before API mode is enabled.

## Recommended MBM integrations

Phound should own the telephony layer. MBM should own:

1. Lead queue and prioritization.
2. Script/playbook generation.
3. Call notes and dispositions.
4. Follow-up scheduling.
5. CRM/pipeline synchronization.
6. Analytics and conversion attribution.
7. AI summaries/action extraction when a supported Phound integration exposes call data.

Keep telephony and business logic separate so the number/provider can change without rewriting the MBM workflow.
