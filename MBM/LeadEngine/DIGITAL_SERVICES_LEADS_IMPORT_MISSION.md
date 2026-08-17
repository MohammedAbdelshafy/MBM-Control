# Digital Services Leads Import Mission

## Objective
Import the exported U.S. digital-services prospect list into the MBM Lead Engine and the live MBM Dialer as a separate monetization lane for low-ticket websites, apps, and recurring maintenance.

## Source
Exported Vibe Prospecting dataset:
- `https://share.explorium.ai/LgBm6M`
- 50 U.S. businesses
- Dataset: `us_digital_service_leads_20260817184607`
- Dataset ID: `ds-84ea72a5-fdeb-4c5b-9771-872229386ad5`

## Offers
- Quick Website: $29 setup + $9/month
- Business Website: $49 setup + $19/month
- Pro Website: $99 setup + $29/month
- Mini App: $149 setup + $39/month
- Business App: $249 setup + $49/month

## Import Rules
1. Do not commit raw PII/contact enrichment into public Git history.
2. Preserve source attribution and import timestamp.
3. Normalize and dedupe by business identity/domain first, phone second when available.
4. Keep this lane separate from real-estate sellers and buyers.
5. Add lead category `DIGITAL_SERVICES` and subcategories `WEBSITE`, `APP`, `MAINTENANCE_UPSELL`.
6. Rank by business intent score, company fit, website/replatform signals, then freshness.
7. Do not fabricate contact information. Missing contact fields remain missing and are eligible for later enrichment through approved pipeline steps.
8. Preserve existing dispositions, notes, attempts, stage, and suppression state if a business already exists.
9. Import operation must be idempotent and safe to rerun.

## Dialer UX
Add a dedicated `Digital Services` lead section/tab with:
- lead name
- domain/website
- state/city
- intent score/topics
- recommended offer
- setup price
- maintenance price
- status: New / Contacted / Interested / Quoted / Won / Lost
- one-click call action where a verified phone exists
- pitch script and objection/closing script

## Lead Engine
Create a canonical ingestion path for digital-services prospects so future searches can feed this category automatically.
Suggested commands:
- `npm run leads:digital-services`
- `npm run leads:digital-services:import`
- `npm run leads:digital-services:rank`

If equivalent commands already exist, consolidate rather than duplicate.

## Verification
Run:
- verification/dialer gate
- relevant unit/integration tests
- `npm run typecheck`
- `npm run build`
- import twice to prove idempotency
- inspect final lead counts and category ordering

## Final Acceptance
Do not mark complete until:
- all 50 exported companies are evaluated for import
- duplicates are reported
- imported count is reported
- rejected/quarantined count is reported
- digital-services category is visible in the dialer
- new digital-service leads are ranked correctly within their category
- existing real-estate queues remain unchanged except for intentional shared dedupe behavior
- live deployment reflects the new section
- exact commit SHA and deployment revision are reported
