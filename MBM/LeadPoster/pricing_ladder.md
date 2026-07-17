# Pricing Ladder & Buyer Strategy ($70 / $150 / $300)

Turns MBM real-estate leads into priced, routed inventory. Driven by
`buyers.yaml` (config-only). `poster.py --post` tags every lead with its tier
and buyer lane; the dry-run prints the distribution.

## Tiers (highest qualifying tier wins)
| Tier | Price | Requires |
|---|---|---|
| **Base** | $70 | any mappable field |
| **Mid** | $150 | verified contact (phone/email) **+** confidence ≥ 60 |
| **Premium** | $300 | mid requirements **+** property signal **+** distress/intent signal |

A lead clears a higher tier only if it meets *all* of that tier's requirements,
so premium inventory is genuinely exclusive/verified/recent/property-rich.

## Recommended lane (start with ONE, not ten)
**Motivated-seller leads → real estate investors & wholesalers.**
Cleanest fit for $70+ if leads are verified, exclusive, recent, signal-rich.

## Outreach angles by buyer lane
- **Investors/wholesalers** — distressed, vacant, absentee, pre-foreclosure,
  high-equity, probate, tired-landlord leads. Channels: investor marketplaces,
  wholesaler FB groups, investor forums, direct outreach to firms.
- **Agents/teams** — exclusive local verified seller leads; LinkedIn + cold email
  to high-performing listing agents / brokerages with paid lead budgets.
- **Mortgage/hard-money** — refi/purchase/investment/distressed owner leads with
  property + equity + timeline data.
- **Home services** — homeowner-owned, high-income, urgent repair leads (roof,
  solar, HVAC, foundation, plumbing, remodel).
- **Legal** — probate/eviction/debt/foreclosure-defense/PI (compliance-heavy).
- **Insurance** — clean, verified, location-specific homeowner/landlord/commercial.
- **B2B SaaS** — business owner / contractor / property-manager / developer leads.

## What sells at $70+
At least 3 of: exclusive · verified contact · high intent · recent activity ·
targeted niche · locality specific · clean data · fast delivery · proof of source ·
deal potential.

## Source-side acquisition stack (Lead Acquisition Monitor)
Priority connectors for *generating* this inventory:
1. NPI Registry · 2. Apollo.io · 3. Shovels.ai · 4. Hunter · 5. PropStream ·
6. Construction permits · 7. BuildZoom · 8. PropertyRadar.
Notable 2026 upgrades: Apollo AI enrichment + trigger-based prospecting;
PropStream integrated dialing + skip-tracing.
