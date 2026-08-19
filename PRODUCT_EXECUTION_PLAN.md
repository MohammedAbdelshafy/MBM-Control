# Revenue-First Execution Plan — First Paying Customer

**Objective:** first paying customer this cycle. Not architecture polish. Sell the thing that already works.

---

## First Product to Sell: **P4 — AI Lead Qualification Agent** (as a DONE-FOR-YOU list-cleaning service)
Why: the gate already works end-to-end (`dialer_verification_gate.py --audit`), needs zero new engineering to deliver, produces an immediately visible result (here's your dead 40%), and is the easiest 5-minute demo. Wrap it with a CSV in → CSV out flow. This is a SERVICE today; the API (Starter/Pro/Agency) is a 2-day build on top.

Second (within 1–2 weeks): **P1 Wholesaler Lead Engine** DFY — the pipeline already produces real, verified leads nightly (code violations + NPI + DCAD owners).

## First Customer Profile
- **Category:** Real estate wholesalers / RE investors or a cold-calling VA agency that buys lead lists.
- **Pain:** bought lists full of dead numbers; reps burn hours; conversion near zero.
- **Existing warm channel:** the company already runs agency outreach (clientHunter, pain-point pipeline) and has a Whop storefront + marketplace listings. Warm prospect = any current Whop/Gumroad buyer or outreach contact in RE.

## Offer
**Done-for-you list clean:** $499/setup — take their existing CSV (any size up to 10k), run the full verification gate, return a scored CSV (VERIFIED / CALLABLE / NOT CALLABLE / DUPLICATE / SUPPRESSED / NEEDS REVIEW) with reason codes + a summary page. 48-hour turnaround. Upsell: monthly qualification subscription + verified lead packs.

## Price anchor
DFY $499 setup · then Starter $49/mo (1k leads/mo) · Pro $149/mo (10k) · Agency $499/mo (100k + API). Path: service → managed → SaaS.

## 5-Minute Demo (P4)
1. Open `dialer_verification_gate.py --audit` output (or uploaded file).
2. Show columns: status, reason code, phone status, verification.
3. Export clean file → done.

## Outreach Message (first send, warm RE list)
> Subject: Your lead list is probably 40% dead — here's proof
>
> Hi {first},
> Most purchased real-estate lists have dead numbers, duplicates, and placeholder records that waste your reps' time. We run every number through a verification gate (real phone, real owner/business, dedupe, DNC-suppression) and return a scored CSV in 48h.
> First 1,000 leads cleaned free. See exactly what's dialable and what isn't.
> Want the proof? Send me your current list.

## Sales process
1. Outreach (warm RE/agency contacts + Whop buyers) → offer free 1,000-lead sample.
2. Sample results page → close DFY $499.
3. Onboarding: upload list → 48h → deliver scored CSV + summary.
4. Upsell to monthly subscription + lead packs + dialer.

## Fulfillment process (P4 today)
- Input: CSV/JSON → `MBM/LeadEngine/dialer_verification_gate.py --file <input>` (or reuse `check_lead` per row).
- Output: scored CSV with `status`, `reason`, `phone_status`, `verification`, plus summary stats.
- Wrap in a tiny runner (no UI needed to sell the DFY first).

## Pipeline also ready to fulfill P1 DFY
- Code violations: `python MBM/LeadEngine/code_violation/daily.py` (sources Dallas/Fort Worth/Arlington/Plano live).
- Verified clinic leads: `python MBM/LeadEngine/npi_verified_callsheet.py`.
- Owners: `dcad_owner_lookup.py` + `property_intel/ownership_verifier.py`.
- Deliver as `lead_pack_builder.py` pack.

---

## Required build tasks (in dependency order)
1. **P4 DFY service + demo — COMPLETE (2026-08-19)**: `productized-service/p4-lead-cleaner/clean_leads.py` wraps the canonical gate into a sellable service — outputs `cleaned.csv` + `summary.json` + `report.md` with statuses VERIFIED/CALLABLE/NOT CALLABLE/DUPLICATE/SUPPRESSED/NEEDS REVIEW, reason codes, dedupe, DNC suppression. Validated on a labeled synthetic sample (11 rows → 3 CALLABLE, 5 NOT CALLABLE, 2 DUPLICATE, 1 SUPPRESSED). Landing page (`landing.html`), revenue dashboard (`revenue_dashboard.html`), campaign tracker with 9 real prospects (`campaign_tracker.md`), and Neteller checkout (DFY $499 / monthly $49 / free sample) all live.
2. **P4 API — COMPLETE**: authenticated Fastify `POST /api/qualify` plus the read-only `npm run leads:qualify` CSV/JSON runner, both using the canonical verification gate.
3. **P1 skip-trace bottleneck — FIXED (2026-08-19)**: removed dead-DNS `openpeoplesearch.org` source from `free_skip_tracer.py` (NXDOMAIN, ~15s per lookup). Remaining sources (TruePeopleSearch, ThatsThem, ZabaSearch, FastPeopleSearch, DuckDuckGo, USPhonebook) verified resolving.
4. **P1 billing + onboarding** (2–3 days): `GET /api/leads` and export are now scoped by `request.user.clientId`; wire Neteller/Whop webhook → `Client.creditsRemaining` and add the onboarding page (market, lead types, volume).
5. **P2 multi-tenant queue + analytics** (3–4 days): tenant-scoped view over `leads_database.json`; call outcome analytics per tenant.
6. **P5 multi-channel intake + lifecycle** (1–2 weeks): web/WhatsApp/form entry, qualification + intent, reschedule/cancel/follow-up/escalate, per-business tenant config.
7. **P3 PDF extractor + supplier DB + Arabic UI** (2–3 weeks): shared document ingest, supplier price store, historical prices, FLAG_FOR_REVIEW, RTL UI.

## Required deployment tasks
1. Stand up Lead Engine Fastify API on a host (VPS/Cloudflare/Fly) with PostgreSQL (or Supabase).
2. Ship P4 service via CSV runner (no server needed for DFY first sale).
3. Deploy `digital-product-store` (Next.js) on Vercel with the 5 landing pages as live product pages.
4. Wire Neteller/Whop checkout → credits (manual grant acceptable for first customers).
5. Move `mbm-dialer/app` + `server/index.js` behind auth for tenant access.
6. Add monitoring/logs for the nightly lead pipelines (already scheduled in `.github/workflows/schedule.yml`).

## Required sales tasks
1. Send the outreach message above to warm RE/agency contacts + existing Whop buyers (use `server/clientHunter.js` or `hunterSend.js`).
2. Run the P4 free-sample offer (1,000 leads) — volume kills objections.
3. Book 5-minute demos for P1/P2 to the same list once P4 closes.
4. Publish the 5 landing pages (copy ready in `PRODUCT_LANDING_PAGES.md`) and route marketplace listings to them.
5. Post proof-of-results (sample audit page) as a Whop/Gumroad listing.

## Current blockers
1. **P4:** no technical blocker — DFY service, demo, landing, checkout, campaign tracker, and 9-prospect batch all live. Next is execution: send outreach. Billing loop behind the API remains optional polish.
2. **P1:** skip-trace dead-DNS host fixed (openpeoplesearch.org removed). Billing loop and onboarding remain. Pipelines already produce real leads nightly.
3. **P2:** multi-tenant queue + analytics unbuilt. Core dialer + scripts live.
4. **P3:** PDF extraction, supplier DB, Arabic UI all unbuilt (biggest effort, highest price).
5. **P5:** multi-channel intake + lifecycle + tenant/billing unbuilt.
6. **Platform:** code-violation enrichment no longer stalls on dead DNS; remaining risk is rate-limits/blocking on the free people-search sources as volume scales.

## 14-day revenue sprint
- Day 1–2: P4 DFY runner + sample clean of a warm contact's list.
- Day 3: send outreach; close first DFY.
- Day 4–7: P4 API live (recurring revenue).
- Day 8–10: P1 tenant scoping + credits; sell P1 DFY to same clients.
- Day 11–14: P2 tenant queue; demo to RE agencies; close second/third customers.
- Every evening: run lead pipelines (they already run via CI) so fresh packs are ready to sell.
