# MBM Acquisition & Lead Generation Research

**Research date:** 2026-10-31  
**Scope:** Acquisition.com and comparable B2B lead-generation, sales-intelligence, GTM workflow, and inbound-conversion models.  
**Purpose:** Turn public market evidence into an actionable MBM LeadEngine strategy.  
**Status:** Research synthesis and proposed operating plan. Vendor claims and anecdotal reports are labelled; this document does not imply MBM has achieved these results.

---

## Executive decision

MBM should not become another bulk lead-list generator or a generic appointment-setting agency. The stronger position is an evidence-led acquisition operator:

1. Identify a narrow customer segment and a problem worth paying to solve.
2. Detect current, observable buying or operational-change signals at the company/account level.
3. Verify the company and source claims before enriching contacts.
4. Qualify the account using fit, signal strength, freshness, authority, contactability, and explicit buying evidence.
5. Offer one small, clearly scoped paid pilot or diagnostic.
6. Use human-led, permission-aware outreach across a few channels.
7. Measure held qualified meetings, proposals, paid pilots, collected cash, and source-level economics.
8. Feed real outcomes back into source and segment ranking.

The immediate engineering priority is the end-to-end path:

provider search → evidence normalization → signal qualification → ranked review queue → approved human outreach → event ledger → outcome feedback

Keep this inside the existing MBM-Control architecture. Do not create another CRM, canonical lead store, queue, event bus, or scoring engine. Preserve DialerSingleWriter.

## 1. What the benchmark businesses actually sell

### Acquisition.com: education-led demand and founder qualification

Acquisition.com is not a contact-data vendor or a conventional outsourced lead-generation agency. Its public site combines free courses, guides, templates, worksheets, content/books, a scaling roadmap, higher-commitment workshops, and a separate portfolio/investment path for selected founders.

Its public lead-generation curriculum covers lead magnets, first clients, content, cold outreach, paid ads, referrals, employees, agencies, and affiliates. The training page describes its courses as free. Its workshop path uses qualification and a booked conversation rather than selling a generic contact list. The site also states that outcomes vary and are not guaranteed.

**What MBM should take from this model:** lead with useful education and a concrete diagnostic asset; give people a reason to raise their hand; then qualify them for the next level. Build a content-to-conversation system, not just a cold list.

Sources:
- https://www.acquisition.com/
- https://www.acquisition.com/training
- https://www.acquisition.com/training/leads
- https://www.acquisition.com/leads-gifts
- https://www.acquisition.com/about-alex-acquisition

### Belkins: managed, multi-channel appointment setting

Belkins sells prospect research, contact verification, outbound campaign execution, and appointment setting. Its service page lists email, LinkedIn, and cold calling, with messaging/WhatsApp follow-up as an add-on. It describes ICP and buyer mapping, list research, copywriting, campaign launch, booking, no-show recovery, reporting, and optimization. Its pricing page advertises an average starting price around $5,000, but that is a vendor-published offer, not an independent guarantee for another business.

**What MBM should take from this model:** do not sell “a list”. Sell a qualified sales outcome with clear inclusion criteria, human verification, a booked/held definition, and transparent reporting.

Sources:
- https://belkins.io/appointment-setting
- https://belkins.io/pricing
- https://clutch.co/profile/belkins

### CIENCE: people + data + process, with held-meeting accountability

CIENCE describes a managed GTM/SDR model that combines phone, email, and LinkedIn. Its public process includes ICP definition, list building and verification, message development, daily SDR activity, qualification before calendar booking, and reporting on held meetings rather than just dials. Its website describes a fixed fee plus compensation tied to held meetings and month-to-month engagement options.

**What MBM should take from this model:** separate activity metrics from commercial outcomes. A meeting booked but never held should not count as a successful qualified outcome.

Source:
- https://www.cience.com/

### Apollo: prospect data and account-level intent

Apollo provides company/contact search, firmographic filters, buying-intent topics, job-posting signals, saved searches, and alerts. Its help documentation is explicit that buying intent belongs to a company; a person surfaced under an intent-matched company is not necessarily personally researching the solution.

**What MBM should take from this model:** an account-level intent signal is a reason to investigate the company, not proof that a specific person wants to buy. Keep company intent, person identity, authority, and permission as separate evidence claims.

Sources:
- https://www.apollo.io/product/prospect
- https://knowledge.apollo.io/hc/en-us/articles/4412658766477-Search-for-Companies
- https://knowledge.apollo.io/hc/en-us/articles/8135721478925-Use-Buying-Intent-to-Prioritize-Prospects
- https://knowledge.apollo.io/hc/en-us/articles/4412665755661-Use-Search-Filters-to-Find-Prospects

### Clay: event signals and multi-source enrichment orchestration

Clay's differentiator is the ability to combine signals, enrich with multiple providers, use AI research, and route context into CRM, email, and other workflows. Its signals pages give examples such as job changes, hiring, website visits, event attendance, social mentions, technology changes, funding, and product-usage events.

Clay has two separate usage meters: Actions for orchestration/execution and Data Credits for marketplace data and AI purchases. Both can be consumed in one workflow. Do not treat a Clay workflow as “free” just because the source data comes from another provider.

**What MBM should take from this model:** maintain a signal registry and provider-cost ledger. Waterfall enrichment should happen only after an account passes the first fit/signal filter.

Sources:
- https://www.clay.com/signals
- https://www.clay.com/pricing
- https://university.clay.com/docs/actions-data-credits

### HubSpot: inbound capture, nurture, qualification, and handoff

HubSpot's lead-generation guidance separates attract, capture, nurture, qualify, and convert. Its form documentation describes creating/updating CRM records and triggering follow-up actions after a visitor submits a form.

**What MBM should take from this model:** every content asset and campaign needs one clear next step, a source/UTM record, a capture mechanism, and a defined qualification/handoff rule.

Sources:
- https://blog.hubspot.com/marketing/beginner-inbound-lead-generation-guide-ht
- https://blog.hubspot.com/sales/lead-generation-funnels-a-complete-guide-for-growing-sales-marketing-teams
- https://knowledge.hubspot.com/forms/create-and-edit-forms

## 2. What the public evidence says about outbound

Do not use one vendor's conversion claims as the universal benchmark.

- Abstrakt reports 6,220,737 outbound dials and 43,758 qualified appointments across its own 2025 client activity. That is roughly 0.70 qualified appointments per 100 dials in that portfolio. It is a large vendor dataset, but still reflects that vendor's client mix and qualification definition.
- ORRJO's 2026 benchmark report gives an average cold-email reply range of 1.9–3.4% and meeting-booked rate of 0.5–1.2% per outreach, while higher-performing programs reportedly outperform this with tight ICP and demand-warmed audiences. Treat this as a directional benchmark, not a target guarantee.
- One 2026 Reddit operator reports six calls booked from 30 posts and 33 comments over ten days. This is one self-reported experiment, not a repeatable market average; it supports testing helpful participation in high-intent communities.
- Another 2026 Reddit operator describes zero real responses after contacting 116 prospects with personalized cold email and low response from LinkedIn. This is another anecdote, but a warning that personalization alone does not repair weak targeting, timing, offer-market fit, or lack of trust.

Sources:
- https://www.abstraktmg.com/state-of-outbound-lead-generation/
- https://orrjo.com/research/state-of-b2b-outbound-2026
- https://www.reddit.com/r/AgencyGrowthHacks/comments/1r5ah5m/6_sales_calls_booked_from_reddit_posts_in_10_days/
- https://www.reddit.com/r/agency/comments/1x6r9xx/whats_actually_working_for_new_client_acquisition/

**MBM measurement rule:** use these sources as priors for an experiment. Replace them with MBM's own cohort data when enough delivered touches and held meetings exist. Track positive replies, negative replies, held meetings, qualified meetings, proposals, paid conversion, and cash collected. Do not optimize on opens alone.

## 3. The acquisition system MBM should build

### A. Pick a narrow ICP and offer

For each campaign, define:
- Vertical and sub-vertical.
- Geography.
- Company-size and operating profile.
- Buyer role and buying committee.
- Problem the offer is designed to address.
- What can be delivered now in a bounded pilot.
- Evidence that would make the offer a poor fit.

Run one primary vertical experiment at a time. Reuse the existing vertical catalog, but make the score and outreach message vertical-specific.

### B. Discover accounts from signals, not just directories

Create a source-backed Account Signal from observations such as:
- New practice/location or additional office.
- Hiring for receptionist, scheduler, intake, appointment coordinator, sales, dispatch, or customer service.
- New service lines, expanded opening hours, or advertised growth.
- Website or booking/contact-flow friction that can be observed directly.
- Public statements about backlog, lead follow-up, admin load, response times, or an active need.
- First-party form submissions, demo requests, inbound conversations, referrals, or opted-in inquiries.

Important distinction: hiring can suggest workload or expansion, but it does not prove missed calls, poor conversion, budget, or intent to buy. Preserve the exact signal and phrase it as a question when contacting the business.

For each signal store the raw claim, source URL or provider object ID, observed/retrieved timestamp, evidence field, confidence, and source type.

### C. Qualify the company before enriching the person

Recommended MBM gates:

1. **ICP fit:** does the company match the campaign's actual buyer profile?
2. **Signal quality:** is there a specific, source-backed trigger or first-party engagement?
3. **Freshness:** is the signal recent enough to matter?
4. **Problem evidence:** is there direct evidence of a problem, or only a proxy such as hiring?
5. **Authority:** is the contact an owner or authorized decision-maker, or merely a person at the company?
6. **Contactability:** can we use a permitted business contact channel with an appropriate source?
7. **Economics:** is the probable deal size and delivery capacity worth the data and outreach cost?

Use separate states for FIT, SIGNAL, PAIN_CONFIRMED, AUTHORITY_CONFIRMED, CONTACT_VERIFIED, and BUYING_INTENT_CONFIRMED. Do not collapse them into one fabricated “hot lead” label.

### D. Use waterfall enrichment only after the first gates pass

Recommended order:
1. Company-level search and fit filtering.
2. Source/website validation.
3. Company buying-signal verification.
4. Decision-maker role discovery.
5. Approved business email or phone verification.
6. Additional paid phone/direct-dial enrichment only when an approved task needs it.

The new Apollo and Explorium adapters in the existing MBM-Control PR are a good start, but raw search results still need to feed the existing evidence-normalization and qualification boundary before an item is considered a qualified acquisition opportunity. Do not push raw provider rows to the live Dialer.

### E. Offer a useful first step, not a giant platform

Build one narrow lead magnet or diagnostic matched to the buyer's problem:
- a short operational readiness assessment;
- a source-backed website/contact-flow review;
- a missed-call/intake workflow checklist;
- a small benchmark or implementation plan;
- a low-risk, fixed-scope paid pilot.

The lead magnet should demonstrate useful thinking. It must not pretend MBM has inspected private call logs, completed implementation, measured customer ROI, or deployed a live production system when it has not.

### F. Multi-channel, human-led conversion

Use:
- Email for concise, source-specific context and a clear opt-out.
- Human-initiated phone calls to publicly listed business lines for discovery.
- Manual LinkedIn research/engagement when useful.
- Helpful, relevant content in communities where target buyers ask questions.
- Referral/partner introductions from businesses already serving the same ICP.
- Inbound landing page/forms for prospects who request the diagnostic or pilot.

Do not make WhatsApp the first cold-contact channel. Use it after the person has provided the number and expressly opted in to receive messages from the named business on WhatsApp.

## 4. The best near-term MBM experiment

### Recommended first campaign: one vertical, one offer, one measurable outcome

Use the existing verified clinic target set as the initial controlled cohort for the Mia Dental OS front-desk / patient-access pilot. This is a recommendation because there is already a specific wedge and a researched clinic list; it is not a claim that those clinics have purchased or admitted a problem.

**Offer framing:** a fixed-scope, human-supervised front-desk / patient-access pilot. State exactly what is included, the duration, clinic requirements, success measures, what remains synthetic/demo-only, and what the pilot does not do. Keep the quoted $500 pilot price separate from collected revenue; revenue is booked only after verified payment evidence.

**Account segmentation:**
- Segment 1: recent opening, expansion, or new provider/location.
- Segment 2: current hiring for front-desk, scheduling, or intake roles.
- Segment 3: visible contact/booking friction on the public website.
- Segment 4: first-party interest, referral, or explicit request.

Do not combine all segments in one message. Each message should reference the actual signal for its segment and ask one discovery question rather than asserting an unverified pain.

**Lead magnet:** a one-page Patient Access & Front-Desk Workflow Check. It should help a practice review call handling, booking handoff, patient intake, and unanswered-inquiry follow-up. The CTA is to request a short walkthrough or pilot-scoping call.

**Primary conversion:** held meeting with a qualified practice decision-maker.  
**Commercial conversion:** signed pilot scope and verified USD payment.  
**Not success metrics:** records found, contacts enriched, emails sent, opens, dials, appointments merely booked, or forecast revenue.

### First 14-day experiment

- Days 1–2: freeze the ICP, offer scope, eligibility rules, and success measure.
- Days 3–4: enrich account signals for the first 20–30 clinics; preserve source and timestamps.
- Days 5–6: build evidence-backed one-page mini-audits and segment-specific call/email scripts.
- Days 7–10: conduct human-led calls and tailored emails; log every disposition and opt-out.
- Days 11–12: follow up only with appropriate prospects; ask for a clear next step.
- Days 13–14: review positive conversations, held meetings, disqualifications, objections, pilot quotes, and cash received. Kill weak segments and expand only the strongest signal/message combination.

The cohort is intentionally small. The objective is to learn which signal and message generate qualified conversations, not to manufacture an impressive lead count.

## 5. MBM's proposed score and queue contract

This is a proposed experiment model, not an externally validated weighting system:

| Dimension | Suggested weight | Rule |
|---|---:|---|
| ICP / company fit | 25% | Must match the campaign's written profile |
| Fresh, specific buying/operational signal | 25% | Needs source, claim, URL/reference, and observed time |
| Problem evidence | 20% | Direct evidence outranks proxy signals |
| Authority / buying committee | 10% | Role must be evidenced; unknown remains unknown |
| Contactability and channel permission | 10% | Public/approved business channel; opt-outs enforced |
| Commercial / timing fit | 10% | Budget, urgency, and timing only when evidenced |

Hard blockers override the numeric score: suppression, stale or unverifiable source, no permitted channel, provider cost not approved, missing company identity, or fabricated intent. A high score must never turn a weak claim into confirmed demand.

Suggested review states:
- DISCOVERED
- EVIDENCE_PENDING
- FIT_REVIEW
- SIGNAL_VERIFIED
- CONTACT_REVIEW
- QUALIFIED_FOR_HUMAN_OUTREACH
- CONTACTED
- CONVERSATION
- MEETING_HELD
- PILOT_PROPOSED
- PAID
- DISQUALIFIED
- SUPPRESSED

Only the existing human/authorization gate can move a record into an outreach-eligible state. Keep the opportunity sidecar isolated from the canonical Dialer database until the authorized handoff.

## 6. Channel priorities for MBM

| Priority | Channel | Why | How to use it |
|---|---|---|---|
| 1 | Human phone + tailored email | Direct path to discovery with a narrow ICP | Call the business line; email only with truthful headers, source-specific relevance, and opt-out |
| 2 | Referrals / channel partners | Trust is transferred and the prospect is pre-contextualized | Identify agencies, consultants, vendors, and advisors already serving the chosen vertical |
| 3 | Helpful community participation | Prospects may publicly describe a problem before entering a sales funnel | Answer specific questions; disclose affiliation; avoid spam, scraping, and unsolicited bulk DMs |
| 4 | Short educational content | Creates compounding trust and supports outbound conversion | Publish one useful problem-specific video/checklist/case analysis per vertical |
| 5 | Inbound landing page + form | Captures people who raise their hand | One offer, one CTA, short form, source/UTM tracking, fast follow-up |
| 6 | Paid acquisition | Scales a proven message but can amplify a bad offer | Do not start until held-meeting and pilot conversion economics are known |

## 7. Compliance and platform rules

These are operational guardrails, not legal advice. Obtain review for the exact campaign, numbers, channels, and jurisdictions before production scale.

- **US commercial email:** CAN-SPAM applies to commercial messages, including B2B email. Use accurate sender/header information, non-deceptive subject lines, required advertising disclosure, a valid physical postal address, a clear opt-out mechanism, and honor opt-outs within 10 business days. Monitor vendors sending on MBM's behalf.
  Source: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- **AI voice / autodialing:** The FCC has confirmed AI-generated human voices fall within TCPA artificial/prerecorded voice restrictions. Do not use AI-generated voice or automated telemarketing calls for cold prospects without documented required consent and legal review. Prefer human-initiated calls for the initial B2B pilot.
  Source: https://docs.fcc.gov/public/attachments/FCC-24-17A1_Rcd.pdf
- **National Do Not Call:** The FTC says its National DNC provisions do not cover ordinary B2B calls, but calls to consumers and personal/mobile numbers can raise different requirements, and FCC rules also apply. Maintain a suppression list and escalate uncertain number types.
  Source: https://www.ftc.gov/business-guidance/resources/complying-telemarketing-sales-rule
- **LinkedIn:** LinkedIn prohibits third-party tools that scrape, copy, or automate site activity, including messages and engagement. Use manual research and human interaction unless an expressly authorized LinkedIn product/API flow applies.
  Sources: https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin and https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software
- **WhatsApp:** Only contact users who provided their mobile number and explicitly opted in to receive messages from the business on WhatsApp; honor opt-outs. Business-initiated platform conversations require approved templates outside the 24-hour customer-service window.
  Sources: https://business.whatsapp.com/policy/preview?lang=es_LA and https://developers.facebook.com/docs/whatsapp
- **Provider spend:** Refresh live credit balances before paid operations. Approval for data spending and permission to access personal contact data are separate gates. Unknown balances or unknown costs remain blocked.

## 8. Recommended implementation sequence in MBM-Control

The current acquisition PR contains live meter adapters and initial guarded search adapters for Apollo and Explorium. The next work should be:

1. Add orchestration that calls provider-specific search adapters with per-operation approvals.
2. Convert returned company claims into the existing EvidenceEnvelope through normalize_provider_record; keep person-level fields withheld until field-level approval exists.
3. Add the account-signal schema and deterministic evidence validator; do not use generic employee-count or industry matches as buying-intent evidence.
4. Score account fit and signal quality with explicit unknowns and hard blockers.
5. Persist only into the existing isolated opportunity/review sidecar; do not write raw provider records to the canonical lead store.
6. Build a reviewable acquisition packet containing source evidence, signal age, company fit, known/unknown authority, offer hypothesis, and one recommended human next action.
7. Record outreach attempts, replies, meetings booked/held, proposals, opt-outs, disqualifications, and payments in the existing event ledger.
8. Recompute source, segment, channel, and offer performance from actual outcomes.

### Highest-value next engineering task

**Build provider-to-evidence-to-review-queue orchestration and one vertical campaign configuration.** That is the bridge between the new provider search APIs and a real qualified acquisition queue. Do not add more vendors until that bridge is tested end-to-end.

---

## Evidence register and limitations

Public source pages checked on 2026-10-31. Vendor product descriptions and pricing are self-published; case studies and headline results may be selected examples rather than representative outcomes. Reddit discussions are anecdotal. Benchmark reports use different channel definitions, time windows, client mixes, and qualification criteria; they are directional only.

Research verdict: **partially confirmed**. The public models support a narrow-ICP, evidence-led, multi-channel acquisition system with value-first capture and outcome-based measurement. Exact conversion performance for MBM's selected vertical and offer remains untested; the 14-day cohort experiment is required before scaling.

Primary source register:
- Acquisition.com: https://www.acquisition.com/training ; https://www.acquisition.com/training/leads ; https://www.acquisition.com/leads-gifts
- Belkins: https://belkins.io/appointment-setting ; https://belkins.io/pricing
- CIENCE: https://www.cience.com/
- Apollo: https://www.apollo.io/product/prospect ; https://knowledge.apollo.io/hc/en-us/articles/8135721478925-Use-Buying-Intent-to-Prioritize-Prospects
- Clay: https://www.clay.com/signals ; https://university.clay.com/docs/actions-data-credits
- HubSpot: https://blog.hubspot.com/marketing/beginner-inbound-lead-generation-guide-ht ; https://knowledge.hubspot.com/forms/create-and-edit-forms
- Outbound benchmarks: https://www.abstraktmg.com/state-of-outbound-lead-generation/ ; https://orrjo.com/research/state-of-b2b-outbound-2026
- Community reports: https://www.reddit.com/r/AgencyGrowthHacks/comments/1r5ah5m/6-sales-calls-booked-from-reddit-posts-in-10-days/ ; https://www.reddit.com/r/agency/comments/1x6r9xx/whats-actually-working-for-new-client-acquisition/
- Compliance: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business ; https://docs.fcc.gov/public/attachments/FCC-24-17A1_Rcd.pdf ; https://business.whatsapp.com/policy/preview?lang=es_LA ; https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin
