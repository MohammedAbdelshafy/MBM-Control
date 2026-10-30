# Provider balance and spend gate

The acquisition router uses the existing provider gateway and budget approval
contract. These adapters add a read-only balance preflight; they do not search,
enrich contacts, export records, send outreach, or write to the canonical lead
store.

## Meter states

- `VERIFIED`: response shape and provider-specific validity checks passed.
- `STALE`: the provider returned a balance but its billing cycle is not active.
- `UNKNOWN`: missing, malformed, internally inconsistent, or failed response.
- `UNCONFIGURED`: no provider credential was supplied.

A paid or unknown-cost operation requires a `VERIFIED` snapshot no older than
120 seconds at both route selection and the final execution gateway. A caller's
approval reference and credit ceiling do not override the meter requirement.
A documented zero-credit operation can proceed without a meter, but contact
field access still requires its separate authorization.

## Provider adapters

| Provider | Read-only meter | Key / status |
|---|---|---|
| Apollo | `POST https://api.apollo.io/api/v1/usage_stats/credit_usage_stats` | `APOLLO_API_KEY`; select an explicit credit pool; the active cycle must include the observation time |
| Explorium / Vibe | `GET https://api.explorium.ai/v1/credits` | `EXPLORIUM_API_KEY`; validates allocated and remaining credits |
| Clay | No authoritative balance endpoint wired | Remains `UNKNOWN`; consult the Clay workspace usage view and supply a separately approved fixed ceiling before any paid operation |

Official API references:

- Apollo API reference: https://docs.apollo.io/reference/view-credit-usage-stats
- Explorium credits endpoint: https://developers.explorium.ai/reference/get_credits
- Clay credit usage: https://university.clay.com/docs/credits-and-usage

## Standard call sequence

```python
from MBM.LeadEngine.connectors.provider_adapters import refresh_provider_candidates
from MBM.LeadEngine.connectors.provider_router import route_provider

refreshed = refresh_provider_candidates(
    candidates,
    required_capability="company_search",
)
decision = route_provider(
    required_capability="company_search",
    candidates=refreshed,
)
```

Use `direct_dial_enrichment`, `phone_enrichment`, or
`mobile_enrichment` only when the approved request actually needs the direct
dial credit pool. Contact-data approval, paid-credit approval, and the daily
agent policy remain independent gates.

Do not persist these snapshots as permanent credit grants. Re-read immediately
before execution. They are observations, not reservations, and vendor balances
can change concurrently.
