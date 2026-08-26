# Connector Batch 2: Revenue + Execution Adapters

## Purpose

Turn the connected-app ecosystem into reusable adapters for MBM Dialer, Social, ConTec, AI Consultancy, and future projects without creating competing sources of truth.

## Authority boundaries

- GitHub: source and release truth.
- Dialer canonical store: authoritative calling eligibility, phone verification, DNC, suppression, queue order, and lead identity state.
- Airtable: operational CRM/intelligence mirror; recommendations and workflow state only.
- Clay / AI Vibe Prospecting: discovery and enrichment evidence only.
- Phound: production telephony execution and provider-derived call events.
- HubSpot: downstream commercial CRM and activity mirror when authorized.
- Supabase: candidate event/state backend for high-volume structured telemetry where appropriate.
- Vercel / AppDeploy / Netlify: deployment and preview surfaces, never data authority.
- Base44 / Lovable / Replit: rapid product/prototype generation; successful work is promoted through GitHub review.
- Figma: UI/design contract, especially the script-first Dialer flow.
- Dropbox: evidence, assets, backups, client deliverables.
- InVideo / B12: media and rapid client-delivery accelerators.
- Asana / Granola: execution context, decisions, and operational tasks.
- CALL-E / Botpress: optional agent/call automation adapters; no fabricated outcomes and no bypass of Dialer safety gates.
- AutoScout24 / ApplyBoard / Nejo / Atlys: vertical/specialized adapters only when a project explicitly uses the related domain.

## Adapter pattern

Every connector integration should expose a small provider-neutral interface:

1. discover
2. enrich
3. verify or score evidence
4. sync/mirror
5. execute
6. receive real events
7. normalize
8. audit

Connectors may fail independently. A failure must downgrade the affected capability, not corrupt canonical data.

## Dialer target flow

Lead discovery → enrichment → evidence → phone/identity verification → canonical Dialer → script/offer → Phound → real provider event → disposition → follow-up → CRM → revenue event.

No connector may create CALL_READY by itself.

## CRM strategy

Use Airtable first for operational visibility and HubSpot when CRM permissions are available. Do not dual-write critical truth without an explicit idempotent event contract.

HubSpot currently requires reauthorization for most write operations in the connected account, so implementation must stay read-only until the user reauthorizes the required permissions.

## Base44 / AppDeploy status

Base44 currently has no user-owned apps exposed through the connected account. AppDeploy exposes separate deployed apps, but none should be assumed to be the MBM Dialer without explicit identity verification. Existing production Dialer deployment remains the authoritative target until mapped.

## Safety gates

- No unverified phone is callable.
- No DNC/suppressed/wrong-party contact is callable.
- No simulated call outcome.
- No index-based conversion outcome.
- No synthetic enrichment presented as fact.
- No connector may shrink canonical lead data.
- All writes are idempotent and auditable.
- Production claims require live verification, not local or test-only evidence.

## Batch 2 implementation order

1. HubSpot read-model and activity mapping after reauthorization.
2. CALL-E optional human-approved outbound/follow-up adapter with real transcripts and outcomes only.
3. Botpress agent adapter for inbound qualification/support, preserving event provenance.
4. Asana/Granola execution-context adapter for project decisions and action history.
5. Base44/AppDeploy/Netlify/Lovable/Replit build-preview adapters once project identity is mapped.
6. Vertical adapters for AutoScout24, ApplyBoard, Nejo, and Atlys without polluting the core Dialer schema.

## Definition of done

A connector is considered integrated only when it is:

DISCOVERED → AUTHENTICATED → CONFIGURED → USED → TESTED → AUDITED → DEPLOYED (when applicable) → LIVE VERIFIED.

If authentication or permissions are unavailable, report the exact blocker and keep the rest of the system operational.
