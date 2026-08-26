# Connector Operating System v1

## Purpose
Create one reusable integration contract for MBM Dialer, MBM Social, ConTec, AI Consultancy, clipping, and future projects. Connectors add capability, but do not silently become competing sources of truth.

## Authority Model

| Layer | Authority | Can write canonical dial eligibility? |
|---|---|---|
| GitHub | Code/release source of truth | No, except reviewed code changes |
| LeadEngine | Verification + canonical persistence | YES |
| Dialer canonical DB | Calling eligibility truth | YES |
| Airtable | CRM/intelligence mirror | NO |
| Clay / Vibe Prospecting | Prospecting + enrichment | NO |
| Phound | Telephony execution + provider events | NO |
| Supabase | Structured events/state where adopted | NO |
| HubSpot / CRM | Commercial pipeline | NO |
| Vercel / Netlify | Deployment | NO |
| Figma | UI/design contract | NO |
| Dropbox | Evidence/archive | NO |
| InVideo / B12 / Lovable / Replit | Build/media acceleration | NO |
| Telegram / Slack | Notifications | NO |

## Universal Flow

DISCOVER -> ENRICH -> VERIFY -> DEDUPE -> SCORE -> SCRIPT -> OFFER -> CALL_READY -> EXECUTE -> DISPOSITION -> FOLLOW_UP -> REVENUE_EVENT -> LEARN -> PACKAGE AS REUSABLE SKILL

## Hard Safety Rules

1. No connector can promote a lead to CALL_READY.
2. No enrichment value is treated as verified without an evidence source and timestamp.
3. No provider execution is treated as a successful outcome without a real provider event.
4. No dashboard reports calls, meetings, offers, or revenue from fixtures or simulations.
5. Airtable is a mirror/CRM layer, never the canonical dialing database.
6. Single-writer protection remains mandatory for canonical lead writes.
7. DNC and suppression always override commercial scoring.
8. Wrong-number and wrong-party outcomes permanently block the current phone until re-verification.

## Connector Adapters

### GitHub
- Branch/PR-based change control.
- CI gates for tests, lint, typecheck, build, security.
- Reusable skills and integration contracts live in `docs/ops` and project skill directories.
- Production changes require live verification evidence.

### Airtable
- Mirror Lead ID, business/contact data, verification metadata, segment, script, offer, stage, next action, and revenue-event IDs.
- Use stable Lead ID as primary merge key.
- Do not use phone as the primary identity key.

### Clay / Vibe Prospecting
- Prospect discovery and enrichment only.
- Store provider/source, enrichment timestamp, confidence, and evidence URL/reference.
- Feed results through LeadEngine verification before Dialer admission.

### Supabase
- Candidate backend for high-volume structured events, event ledger, realtime state, tenant isolation, and Edge Functions.
- RLS/security advisors required before production adoption.

### Phound
- Production telephony provider.
- Call creation, status, webhook/event normalization, disposition evidence.
- No simulation path.

### Vercel / Netlify
- Deployment targets.
- Deployment SHA must be traceable to GitHub.
- Live endpoint verification required after release.

### Figma
- UX contract for rep workflow.
- Dialer order: Summary -> Evidence -> Verified Contact -> Script -> Offer -> Dial -> After-call -> Follow-up.

### Dropbox
- Evidence, raw imports, client deliverables, media, backups, and release artifacts.
- Do not use as canonical transactional state.

### InVideo / B12 / Lovable / Replit
- Accelerate media, websites, prototypes, and experiments.
- Successful output is promoted through GitHub before becoming production architecture.

## Reusable Skill Promotion

Every completed integration should produce:

- connector contract
- adapter/config schema
- smoke test
- failure modes
- security notes
- rollback procedure
- example workflow
- measurable success criteria

## Cross-Project Reuse

The same connector contracts should be reusable by:

- MBM Dialer
- MBM Social
- ConTec Real Estate AI Media
- AI Consultancy
- Clipping Factory
- future verticals

## Current Production Note

The repository README currently names `https://mbm-dialer.higgsfield.app/` as the canonical deployment. Production verification work has also used the Vercel deployment. This is a deployment-control issue, not a data-authority rule. The next release must establish one explicit canonical public URL and update documentation accordingly.
