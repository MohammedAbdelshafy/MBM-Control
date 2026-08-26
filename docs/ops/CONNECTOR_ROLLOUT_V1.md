# Connector Rollout v1

## Batch 1: Revenue Data Foundation

1. Airtable stable Lead ID mirror and CRM fields.
2. Clay/Vibe enrichment adapter contract.
3. Verification evidence schema.
4. Supabase event-ledger evaluation.
5. Phound provider event contract.

## Batch 2: Product/UX and Delivery

1. Figma rep-workflow contract.
2. Lovable UI iteration lane.
3. Replit rapid-service lane.
4. Netlify preview lane.
5. Vercel production lane.

## Batch 3: Acquisition and Media

1. InVideo media production.
2. B12 rapid client-site delivery.
3. MBM Social attribution.
4. Dropbox evidence/archive.

## Batch 4: Vertical Intelligence

1. Investment-banking research skill pack.
2. Public-equity research skill pack.
3. AutoScout24 automotive vertical.
4. ConTec real-estate media adapters.

## Per-Connector Gate

READ -> MAP -> DRY RUN -> TEST -> REVIEW -> ENABLE -> LIVE VERIFY -> MEASURE -> DOCUMENT -> REUSE

## Never Do

- Do not bulk-copy the full canonical Dialer database into third-party systems without a field map and dedupe policy.
- Do not give enrichment providers authority to call leads.
- Do not treat a successful API request as a business outcome.
- Do not activate production webhooks or outbound automation without a defined owner, event schema, retry policy, and kill switch.
- Do not merge connector work directly to master without CI and live verification evidence.

## Handoff Rule

Once Batch 1 passes, the same connector registry and skill contracts are reused by the next project instead of reimplementing integrations.
