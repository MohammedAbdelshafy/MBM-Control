# Olivia Schremmer — Reverse Engineering Report

**Date:** 2026-08-27
**Confidence Legend:** VERIFIED | STRONG INFERENCE | UNVERIFIED

---

## 1. PERSONA PROFILE

| Field | Data | Confidence |
|---|---|---|
| Name | Olivia Schremmer | VERIFIED |
| Brand | "The Wholesale Girl" | VERIFIED |
| Role | Dispo Agent (Disposition Specialist) | VERIFIED |
| Company | Schremmer Solutions LLC | VERIFIED |
| Location | Gorham, Kansas | VERIFIED |
| Active Since | January 2024 | VERIFIED |
| Education | BS Biology | VERIFIED |
| Affiliation | MaxDispo (Disposition Company) | VERIFIED |

---

## 2. TACTIC EXTRACTION

### TACTIC 001: Disposition-as-a-Service via MaxDispo

| Field | Detail |
|---|---|
| Source | maxdispo.com, dashboard.maxdispo.com |
| Platform | Web dashboard |
| Tactic | Submit deals → automated underwriting → buyer matching via InvestorLift Cartel Mode (5M+ buyers) → phone/text blasts → close in 72hrs |
| Target | Wholesalers with contracts but no buyer list |
| Trigger | Wholesaler has a signed contract, needs buyers |
| Hook | "Sell Your Deal in 72 Hours or Less" |
| CTA | Submit deal form |
| Acquisition mechanism | Deal submission form → underwriting → JV agreement |
| Qualification mechanism | Contract status verification, deal economics review |
| Monetization mechanism | JV split on assignment fee (typically 50/50) |
| Confidence | VERIFIED |
| Automation potential | HIGH — dashboard, InvestorLift API, automated scoring |
| System feature | Deal submission portal, real-time tracking, automated buyer matching |

### TACTIC 002: JV Wholesaling Model

| Field | Detail |
|---|---|
| Source | MaxDispo, DispoBridge, multiple industry sources |
| Platform | Written agreements per deal |
| Tactic | Deal-bringer (contract) + Dispo partner (buyers) = 50/50 JV split |
| Target | Wholesalers who can get contracts but can't move them |
| Trigger | Signed contract with disposition deadline pressure |
| Hook | "Don't leave money on the table — let us find your buyer" |
| CTA | JV agreement signed → deal flows through dispo pipeline |
| Acquisition mechanism | Contract submission + JV agreement |
| Qualification mechanism | Contract validity, deal economics, timeline |
| Monetization mechanism | Assignment fee split (50/50 standard, 60/40 weighted) |
| Confidence | VERIFIED |
| Automation potential | MEDIUM — template-based agreements, status tracking |
| System feature | JV agreement generator, split calculator, timeline tracking |

### TACTIC 003: Instagram DM Qualification Funnel

| Field | Detail |
|---|---|
| Source | IGMsg, Krista Mashore, BAM/Conover framework |
| Platform | Instagram |
| Tactic | Comment triggers → automated DM → conversational qualification → call booking |
| Target | Motivated sellers, buyers, JV partners |
| Trigger | Post engagement (comments like "DEAL", "SELL", "BUY") |
| Hook | Curiosity + money mechanism ("you don't need to own the property") |
| CTA | Reply to DM → qualification questions → book call |
| Acquisition mechanism | Social engagement → DM → qualification → CRM entry |
| Qualification mechanism | 3-step DM script: Connect → Qualify → Convert |
| Monetization mechanism | Lead enters pipeline → deal → assignment fee |
| Confidence | VERIFIED |
| Automation potential | HIGH — ManyChat/InstantDM auto-replies, CRM sync |
| System feature | Social CTA routing, DM-to-lead pipeline, qualification bot |

### TACTIC 004: Buyer Segmentation Protocol

| Field | Detail |
|---|---|
| Source | Deal Run, Televista, BiggerPockets |
| Platform | Internal CRM |
| Tactic | 3-tier buyer activation: Hot (2-4hr head start) → Engaged (email blast) → Broader (day 3+) |
| Target | Buyer list |
| Trigger | New deal locked under contract |
| Hook | "New deal in [market] — [price] — [type]" |
| CTA | Reply with offer / book showing |
| Acquisition mechanism | Deal sheet distribution with segmented timing |
| Qualification mechanism | Response speed, offer quality, close history |
| Monetization mechanism | Fastest path to assignment close |
| Confidence | VERIFIED |
| Automation potential | HIGH — automated CRM segmentation + timed distribution |
| System feature | Buyer tier engine, timed deal distribution, engagement tracking |

### TACTIC 005: Content-to-Lead Pipeline

| Field | Detail |
|---|---|
| Source | GrowthLimit, MotivatedLeads, multiple content marketing sources |
| Platform | Instagram, YouTube, Facebook, Blog |
| Tactic | High-intent content (seller pain points) → lead capture → qualification → deal |
| Target | Motivated sellers searching "sell house fast", "sell inherited house" |
| Trigger | Content impression → engagement → CTA response |
| Hook | Pain-point headlines: "5 Reasons Your House Isn't Selling", "Sell As-Is" |
| CTA | DM, form fill, phone call |
| Acquisition mechanism | Content → SEO/social distribution → landing page → lead form |
| Qualification mechanism | Intent signals (keyword, engagement depth, form completeness) |
| Monetization mechanism | Lead → seller pipeline → contract → assignment |
| Confidence | VERIFIED |
| Automation potential | MEDIUM — content scheduling, form routing, but creation is human |
| System feature | Content attribution tracking, lead source routing, intent scoring |

### TACTIC 006: Deal Scoring (MAO / 70% Rule)

| Field | Detail |
|---|---|
| Source | Multiple wholesaling sources, SOS CRM Deal Wizard |
| Platform | Internal calculation |
| Tactic | MAO = (ARV × 0.70) - Estimated Repairs. Score deals on margin, demand, timeline |
| Target | Incoming deals from any source |
| Trigger | Deal submitted with address + basic data |
| Hook | Transparent score: "This deal scores 72/100 — here's why" |
| CTA | Proceed to buyer matching / request more data |
| Acquisition mechanism | Automated underwriting on submission |
| Qualification mechanism | Data completeness check + margin calculation + demand lookup |
| Monetization mechanism | Better deals → faster closes → higher revenue |
| Confidence | VERIFIED |
| Automation potential | HIGH — deterministic calculation, no AI needed for core scoring |
| System feature | Deal scoring engine, data completeness gate, margin calculator |

### TACTIC 007: Buyer Demand Signals

| Field | Detail |
|---|---|
| Source | InvestorLift, MaxDispo, WholesalerHQ |
| Platform | Internal analytics |
| Tactic | Track which buyer segments are most active, which are submitting offers, which are closing |
| Target | Internal decision-making |
| Trigger | Deal submission → demand lookup → acquisition guidance |
| Hook | "Houston SFR $150-250K Flip — DEMAND: HOT, 37 active buyers" |
| CTA | Source more deals in hot segments |
| Acquisition mechanism | Demand data feeds back into seller acquisition targeting |
| Qualification mechanism | Buyer activity metrics (offers, closings, response times) |
| Monetization mechanism | Focus on hot demand → higher close rates → more revenue |
| Confidence | STRONG INFERENCE |
| Automation potential | HIGH — aggregate buyer behavior data automatically |
| System feature | Demand dashboard, segment heat maps, acquisition recommendations |

### TACTIC 008: Social Proof + Case Study Content

| Field | Detail |
|---|---|
| Source | Olivia's Instagram, YouTube appearances |
| Platform | Instagram, YouTube |
| Tactic | Show real deals, real numbers, real dispositions to build credibility |
| Target | Sellers, buyers, JV partners |
| Trigger | Scrolling social feed |
| Hook | "Just closed this deal for $XX,XXX — here's how" |
| CTA | "DM me DEAL if you have a property" / "DM BUY if you want access" |
| Acquisition mechanism | Social proof → trust → engagement → DM → pipeline entry |
| Qualification mechanism | Self-selection based on CTA keyword |
| Monetization mechanism | More leads → more deals → more revenue |
| Confidence | VERIFIED |
| Automation potential | LOW — content creation is human, but routing can be automated |
| System feature | Content → lead routing by CTA keyword |

---

## 3. ATTENTION MECHANISMS IDENTIFIED

| Mechanism | Example | Confidence |
|---|---|---|
| Contradiction | "You don't need to own property to make money in RE" | VERIFIED |
| Money mechanism | "Assignment fees of $10K-$30K per deal" | VERIFIED |
| Proof/Casestudy | Real deal walkthroughs with numbers | VERIFIED |
| Myth busting | "Wholesaling isn't illegal — here's why" | VERIFIED |
| Hidden opportunity | "There are motivated sellers in every market" | STRONG INFERENCE |
| Curiosity gap | "The #1 mistake new wholesalers make" | STRONG INFERENCE |

---

## 4. CAPTURE MECHANISMS IDENTIFIED

| Mechanism | Target | Confidence |
|---|---|---|
| Instagram comment → DM | Sellers, buyers | VERIFIED |
| Skool community ($25/mo) | New wholesalers | VERIFIED |
| Deal submission form | Wholesalers with contracts | VERIFIED |
| Linktree hub | All audiences | VERIFIED |
| YouTube appearances | Broader RE audience | VERIFIED |
| Facebook groups | Buyers, sellers | VERIFIED |

---

## 5. QUALIFICATION MECHANISMS IDENTIFIED

| Mechanism | Data Collected | Confidence |
|---|---|---|
| DM script (Connect→Qualify→Convert) | Location, pain, timeline, budget | VERIFIED |
| Deal submission form | Address, contract status, price, ARV, repairs | VERIFIED |
| Buy box capture | Market, price, type, strategy, rehab tolerance | VERIFIED |
| Self-selection via CTA | Intent type (DEAL/SELL/BUY/JV) | VERIFIED |

---

## 6. MONETIZATION MECHANISMS IDENTIFIED

| Mechanism | Revenue Path | Confidence |
|---|---|---|
| JV assignment split | 50/50 on assignment fee | VERIFIED |
| Disposition service fee | Fee for finding buyers | STRONG INFERENCE |
| Education/community | Wholesailors Academy $25/mo | VERIFIED |
| Consulting | Deal-by-deal partnerships | STRONG INFERENCE |

---

## 7. WHAT TO BUILD (System Features)

Based on verified tactics, the system needs:

1. **Deal Submission Portal** — MaxDispo-style intake with underwriting
2. **Buyer Buy Box Engine** — Structured buyer profiles with matching
3. **Buyer Demand Dashboard** — Real-time demand signals by segment
4. **Deal Scoring Engine** — Deterministic MAO/margin scoring
5. **Social CTA Routing** — Keyword-based lead routing from social
6. **DM Qualification Flow** — Conversational qualification sequences
7. **Buyer Segmentation** — 3-tier timed deal distribution
8. **JV Agreement Generator** — Template-based agreements
9. **Disposition Pipeline** — Kanban: Available → Marketing → Matched → Assigned → Closed
10. **Content Attribution** — Track which content produces revenue

---

## 8. WHAT NOT TO BUILD

| Item | Reason |
|---|---|
| Education/course platform | Out of scope — not core RE pipeline |
| InvestorLift clone | Use existing tools, integrate via API |
| Social media content creator | Human-driven, not system feature |
| Phone/voice AI agent | Existing mbm-dialer covers this |
| Escrow/title integration | Requires licensed third parties |
