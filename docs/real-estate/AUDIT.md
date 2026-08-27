# AUDIT.md — Existing System Audit

**Date:** 2026-08-27

---

## EXISTING ENTITIES (Prisma Schema)

| Entity | Status | Notes |
|---|---|---|
| Property | EXISTS | Full schema: parcelId, address, propertyType, estimatedValue, lat/lng |
| Owner | EXISTS | ownerType, isAbsentee, confidenceScore, verificationStatus |
| Lead | EXISTS | 15 NicheTypes, status, grade, score, callabilityScore |
| LeadScore | EXISTS | 8-factor breakdown |
| BuyerProfile | EXISTS | targetGeographies, priceMin/Max, minSpread, activeCapital |
| BuyerMatch | EXISTS | matchScore, reason, status |
| Deal | EXISTS | dealType, grossRevenue, netCommission, netellerPaymentId, status |
| Call | EXISTS | durationSeconds, disposition, recordingUrl, transcript |
| Disposition | EXISTS | type (BAD_NUMBER/DNC/SOLD/etc), permanent flag |
| Auction | EXISTS | auctionDate, openingBid, estimatedValue |
| OutreachCampaign | EXISTS | leadFilters, templateIds, sentCount, openRate, replyRate |
| OutreachTemplate | EXISTS | type, subject, body, variables |
| Pipeline | EXISTS | steps (JSON), schedule, lastRunAt |
| ScoringConfig | EXISTS | weights (JSON), scope |

---

## EXISTING ENGINES (Python)

| Engine | Status | Location | Notes |
|---|---|---|---|
| buyer_matching_engine.py | EXISTS | MBM/LeadEngine/ | Property-to-buyer matching, 100pt scoring |
| buyer_discovery_engine.py | EXISTS | MBM/LeadEngine/ | Active buyer discovery from CSV |
| seller_motivation_scorer.py | EXISTS | MBM/LeadEngine/ | Multi-signal distress scoring 0-100 |
| lead_quality_scorer.py | EXISTS | MBM/LeadEngine/ | 8-factor transparent scoring |
| offer_recommendation_engine.py | EXISTS | MBM/LeadEngine/ | Industry-specific offer recs |
| canonical_deal_engine.py | EXISTS | MBM/LeadEngine/ | 16-stage deal memory, Neteller-linked |
| dialer_queue_engine.py | EXISTS | MBM/LeadEngine/ | 7 canonical queue buckets |
| dialer_script_engine.py | EXISTS | MBM/LeadEngine/ | 15-segment call scripts |
| dialer_verification_gate.py | EXISTS | MBM/LeadEngine/ | Owner-verified numbers only |
| property_intel/pipeline.py | EXISTS | MBM/LeadEngine/ | Full property intelligence pipeline |
| property_intel/scoring.py | EXISTS | MBM/LeadEngine/ | Opportunity + callability scoring |
| pain_to_offer/schema.py | EXISTS | MBM/LeadEngine/ | 21-state pipeline with evidence gates |

---

## EXISTING UI

| Component | Status | Location | Notes |
|---|---|---|---|
| AutoDialer.jsx | EXISTS | src/pages/ | Full dialer with scripts, WHOLESALER_RESOURCES |
| MobileDialer.jsx | EXISTS | src/pages/ | Mobile dialer with Phound links |
| DealingRoom.jsx | EXISTS | src/pages/ | Deal pipeline board (construction-focused) |
| MasterScript.tsx | EXISTS | mbm-dialer/ | 818-line dialer component |
| MBMDashboard.jsx | EXISTS | src/pages/ | Operations dashboard |

---

## EXISTING INTEGRATIONS

| Service | Status | Notes |
|---|---|---|
| Neteller | ACTIVE | Canonical payment rail |
| NPI Registry | ACTIVE | Real healthcare businesses |
| DCAD ArcGIS | ACTIVE | Dallas ownership verification |
| Phound | ACTIVE | SMS via native app |
| Supabase | ACTIVE | Edge Functions + DB |
| Groq | ACTIVE | LLM inference |
| Auction.com | BLOCKED | Incapsula anti-bot |
| RapidAPI | BLOCKED | 429 rate limits |
| Twilio | DEAD | SMS not working |

---

## MISSING (Gap Analysis)

| Gap | Impact | Priority |
|---|---|---|
| No Supabase property tables deployed | Data has no persistent home | P0 |
| No live buyer database | buyer_contacts.csv is legacy | P0 |
| No ARV/comps data source | Can't calculate MAO automatically | P0 |
| No deal submission portal | No intake for deal sources | P0 |
| No disposition pipeline UI | DealingRoom is construction-focused | P1 |
| No buyer demand dashboard | Can't see what buyers want | P1 |
| No social CTA routing | Social leads go nowhere | P1 |
| No content attribution | Can't track which content makes money | P2 |
| No JV agreement generator | Manual process | P2 |
| No appointment booking UI | api/meeting.js exists but no frontend | P2 |
| No wholesale contract generation | MBM/Wholesale/ has only 2 docs | P2 |
| No MLS/Zillow/Redfin API | No property data enrichment | P3 |

---

## DUPLICATED

| Pattern | Locations | Resolution |
|---|---|---|
| Lead schema | canonical_lead_schema.py, prisma, MasterScript.tsx, JSON | Use Prisma as source of truth |
| Neteller builder | 3 Python + 1 Node + 1 Python fallback | Keep canonical_lead_schema.py + server/neteller.js |
| Scoring engines | 5 separate | Consolidate into deal_scoring_engine.py |
| Queue files | 4 JSON files | Consolidate into Prisma |
| Deal stages | 3 different enums | Use canonical_deal_engine.py stages |

---

## QUICK WINS

| Asset | Leverage |
|---|---|
| Prisma schema | Already has Property, Lead, BuyerProfile, BuyerMatch, Deal — deploy to Supabase |
| buyer_matching_engine.py | Already has 100pt scoring — extend with price matching |
| seller_motivation_scorer.py | Production-ready — use as-is |
| canonical_deal_engine.py | 16-stage pipeline — extend for wholesale deals |
| dialer_queue_engine.py | 7-bucket queue — reuse for wholesale pipeline |
| dialer_verification_gate.py | Quality gate — reuse for buyer verification |
| AutoDialer.jsx | Already has WHOLESALER_RESOURCES — extend for dispo |
| mbm-dialer app | Full dialer UI — add disposition views |

---

## RECOMMENDATION

**Do NOT rebuild.** The Prisma schema already has 80% of what we need. The path forward:

1. Deploy Prisma schema to Supabase (persistent storage)
2. Build `buyer_buy_box_engine.py` — extend BuyerProfile with structured buy box
3. Build `deal_scoring_engine.py` — consolidate 5 scoring engines into 1
4. Build `buyer_match_engine.py` — extend existing with price/ARV matching
5. Build `deal_submission_engine.py` — new intake portal
6. Build `buyer_demand_engine.py` — aggregate buyer signals
7. Wire social CTA routing into existing Lead model
8. Build disposition pipeline as new React page (not modify DealingRoom)
