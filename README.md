# MBM Autonomous Operating System & Control Plane

> **Autonomous AI Agency & Lead Intelligence Platform** — Revenue-ready demonstration assets: verified healthcare B2B call sheets (CMS NPI registry, zero synthetic), autonomous video production pipeline (Crayo-class 9:16 reframe + subtitle engine), and Dallas County property ownership verification (DCAD ArcGIS live match). All claims are evidence-backed; see `docs/COMMERCIAL_TRUE_STATE.md` and `docs/GITHUB_REVENUE_READINESS.md`.

---

### Commercial Capabilities & Demonstration Assets

| Capability | Target Client | Delivery Mechanism | Verification & Provenance | Payment Rail |
|---|---|---|---|---|
| **1. Healthcare B2B Call Sheets** | Healthcare agencies & medical SaaS | Sanitized CSV + Brief + Manifest ([Sample CSV](docs/samples/sample_healthcare_callsheet.csv)) | CMS NPPES v2.1 + Luhn NPI checksum + NANP phone validation *(not live-dialed)* | Neteller Invoice (`abdelshafyclapps@gmail.com`) |
| **2. Crayo-Class Content Engine** | Podcasters, creators & brands | Autonomous 9:16 edit + animated captions ([Sample Spec](docs/samples/crayo_clip_production_spec.json)) | 8-axis virality scoring + ffmpeg auto-crop; YouTube Studio publish | Whop Storefront (`prod_MaHYZkh3AfEEf`) |
| **3. DCAD Property Ownership Intel** | Wholesalers & real estate investors | Verified parcel APN + Deed owner dossier ([Sample Dossier](docs/samples/sample_dcad_deed_audit.md)) | Dallas County (DCAD) tax roll ownership matching | Neteller Invoice (`abdelshafyclapps@gmail.com`) |

*For commercial true state and verified evidence, view [`docs/COMMERCIAL_TRUE_STATE.md`](docs/COMMERCIAL_TRUE_STATE.md) and [`docs/SALES_EVIDENCE_PACK.md`](docs/SALES_EVIDENCE_PACK.md).*

---

## Commercial Subsystems (Evidence-Based)

All three subsystems have passing hermetic test suites and verifiable data sources. **Revenue status: DEMO_READY / YELLOW GATE** (not yet live-transacting; Whop checkout requires reconciliation). See `docs/GITHUB_REVENUE_READINESS.md` for full audit.

- **Healthcare B2B Practice Call Sheets** (`MBM/LeadEngine/nppes/`): CMS NPPES federal registry source, zero-synthetic provenance gate (`LeadProvenanceGate`), NANP-validated E.164 format. 45 passing tests. **Not live-carrier verified**. Price hypothesis: $199–$497.
- **Crayo-Class Video Engine** (`clipping-factory/MBM-Social/mbm_social/crayo_engine.py`): 9:16 ffmpeg reframe, word-level subtitle burn-in, 8-axis virality scoring. 24 passing tests. YouTube Studio auto-publish supported; TikTok/Instagram manual upload only.
- **Property Ownership Intelligence** (`MBM/LeadEngine/property_intel/`): DCAD ArcGIS live ownership verification, CONFLICT-safe ambiguity handling. 83 passing tests. **Live auction scrape blocked by Imperva/Incapsula** (documented, not papered over). Owner identification requires working APN.

---

## Base44 Development

Use this repository to run and edit the app locally, then publish changes back through Base44. Any change pushed to the repo will also be reflected in the Base44 Builder.

### MBM Dialer

- **Canonical live deployment:** https://mbm-dialer.higgsfield.app/
- **Mobile dialer route:** https://mbm-dialer.higgsfield.app/dialer/mobile
- **Workflow:** The mobile workflow is designed around Phound as the calling app: copy a lead's normalized number or hand off to Phound, then return to MBM for scripts, dispositions, notes, and follow-up.

## Prerequisites

1. Clone the repository using the project's Git URL.
2. Navigate to the project directory.
3. Install dependencies: `npm install`.
4. Install the Base44 CLI: `npm install -g base44@latest`.

See the [Base44 CLI docs](https://docs.base44.com/developers/references/cli/get-started/overview) if you want to run Base44 commands directly.

## Run Locally

Run the full local development environment from the project root:

```bash
base44 dev
```

`base44 dev` starts the local Base44 development backend and, when this app is configured for it, also starts the frontend dev server for you. Use the frontend URL printed by the command.

For example, when the Base44 project config includes a `serveCommand`, `base44 dev` can launch the frontend too:

```json5
{
  "site": {
    "serveCommand": "npm run dev"
  }
}
```

In a Base44 project this lives in `base44/config.jsonc`.

## Run Only The Frontend

If you only want to work on the frontend against the hosted Base44 backend, run:

```bash
npm run dev
```

Open the local URL printed by Vite.

## Use The Hosted Backend

For frontend-only development, create or update `.env.local` in the project root:

```bash
VITE_BASE44_APP_ID=your_app_id
VITE_BASE44_APP_BASE_URL=https://your-app.base44.app
```

`VITE_BASE44_APP_ID` identifies the Base44 app.

`VITE_BASE44_APP_BASE_URL` tells the Base44 Vite plugin where to send local `/api` requests. Point it at your deployed Base44 app URL when you want the local frontend to use the hosted Base44 backend.

When you use `base44 dev`, the command injects the local Base44 values for you, so `.env.local` is mainly needed for frontend-only workflows.

## Publish Your Changes

After pushing your changes to git, open the Base44 dashboard and publish the app:

```bash
base44 dashboard open
```

## Docs & Support

Documentation: [https://docs.base44.com/Integrations/Using-GitHub](https://docs.base44.com/Integrations/Using-GitHub)

Base44 CLI command reference: [https://docs.base44.com/developers/references/cli/commands/introduction](https://docs.base44.com/developers/references/cli/commands/introduction)

Support: [https://app.base44.com/support](https://app.base44.com/support)
