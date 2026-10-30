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


## Search adapters

The guarded search clients are exported from `MBM.LeadEngine.connectors`:

- `search_apollo_organizations`: `POST /api/v1/mixed_companies/search`, exactly one Apollo credit per page; the adapter limits pages to 100 records and requires an approval reference plus fresh lead-credit balance.
- `search_apollo_people`: `POST /api/v1/mixed_people/api_search`, zero credits; Apollo says this endpoint does not return phone or email. It still requires separate contact-data approval and an approval reference because the returned people records identify individuals.
- `fetch_explorium_businesses`: `POST /v1/businesses`, variable cost; each call requires a fresh shared Explorium balance and a positive, caller-approved maximum credit ceiling.
- `fetch_explorium_prospects`: `POST /v1/prospects`, variable cost; same meter and ceiling, plus separate contact-data approval before even reading the meter.

All four accept caller-supplied, JSON-compatible filters and preserve the provider records, endpoint, retrieval timestamp, page details, and provider request/correlation reference. Empty filters and unbounded paging are rejected. Results are returned to the caller only; no records are written into Dialer or the canonical lead store.

Official API references:

- Apollo organization search: https://docs.apollo.io/reference/organization-search
- Apollo people search: https://docs.apollo.io/reference/people-api-search
- Apollo pricing and credit usage: https://docs.apollo.io/docs/api-pricing
- Explorium fetch businesses: https://explorium-api.readme.io/reference/fetch_businesses
- Explorium fetch prospects: https://explorium-api.readme.io/reference/fetch_prospects
- Explorium active credit summary: https://explorium-api.readme.io/reference/get_active_credits_summary
