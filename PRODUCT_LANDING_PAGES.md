# Tier-A Landing Pages + Offers + Demo Flows

Copy is concrete (problem → solution → how it works → demo → features → result → pricing → CTA). No "AI-powered transformation" filler. Each maps to a 5-minute prospect demo.

---

## 1. AI Real Estate Wholesaler Lead Engine

**PROBLEM:** Wholesalers waste 20+ hrs/wk pulling county records, verifying owners, and hunting code violations — then dial dead numbers.

**SOLUTION:** Verified, sourced, scored wholesale leads delivered fresh — with real owners from county records and real business phones from the CMS NPI registry. No fabricated data, ever.

**HOW IT WORKS**
1. You pick market + lead type + volume.
2. Pipelines pull live code-violation, county-ownership, and NPI sources nightly.
3. Every lead passes verification + provenance + dedupe + suppression gates.
4. You get a fresh callable queue with source, verification status, phone status, priority, and freshness.

**DEMO (5 min):** market dropdown → filters (distressed/absentee/vacant/cash-buyer) → live verified leads → phone status + score → export CSV → send to dialer.

**FEATURES:** choose market · lead types · volume · verified leads · quality view · filters · export · send-to-dialer · freshness · source · verification status · phone status · priority · usage tracking.

**RESULT:** 100 verified, de-duplicated, suppression-screened leads per month instead of 1,000 dead records.

**PRICING**
| | STARTER | PRO | AGENCY |
|---|---|---|---|
| Setup | $0 | $0 | $500 |
| Monthly | $297 | $597 | $1,197 |
| Verified leads/mo | 100 | 500 | 1,500 |
| Markets | 1 | 3 | 10 |
| Export | CSV | CSV+Excel | CSV+Excel+JSON+API |
| Dialer push | no | yes | yes + white-label |
| Support | email | email+chat | dedicated |

**DONE-FOR-YOU:** $1,997/mo — we operate the dialer and hand you qualified seller conversations weekly.

**CTA:** "Get your first 100 verified leads in 48 hours" → book demo.

---

## 2. AI Cold Calling Assistant

**PROBLEM:** Reps don't know who to call, what to say, or what happened on the last call.

**SOLUTION:** A call workspace with a freshness-ranked queue and segment-aware scripts — separate real-estate-seller scripts from B2B sales scripts — plus dispositions, callbacks, and analytics.

**HOW IT WORKS**
1. Fresh-lead queue orders calls (FRESH_CALL_NOW → FRESH_NEXT → verified → rest).
2. Lead profile shows source, verification, score, and script.
3. Tap-to-call via your phone (Twilio bridge / Phound).
4. Log outcome → disposition → callback/follow-up scheduled automatically.

**DEMO (5 min):** open queue → pick top fresh lead → script auto-selected for its segment → tap call → log disposition → follow-up appears.

**SEGMENT SCRIPTS (verified in `dialer_script_engine.py`):** DISTRESSED_SELLER · ABSENTEE_OWNER · VACANT_PROPERTY · HIGH_EQUITY · FREE_AND_CLEAR · TIRED_LANDLORD · OUT_OF_STATE_OWNER · LIKELY_TO_MOVE · BUSINESS_OWNER · B2B · AGENCY · CONTRACTOR. Real-estate scripts never leak into B2B calls and vice-versa.

**FEATURES:** lead queue · fresh leads · priority queue · caller workspace · lead profile · script selection · objection handling · call outcome · notes · callbacks · follow-ups · dispositions · analytics.

**RESULT:** reps double talk-time on fresh, verified, scripted leads.

**PRICING**
| | STARTER | PRO | AGENCY |
|---|---|---|---|
| Setup | $0 | $0 | $500 |
| Monthly | $199 | $499 | $999 |
| Seats | 1 | 3 | 10 |
| Call minutes | 500 | 2,000 | 10,000 |
| CRM + dispositions | yes | yes | yes + white-label |
| Analytics | basic | full | full + exports |
| Support | email | chat | dedicated |

**DONE-FOR-YOU:** $1,499/mo — we run your outbound campaigns end-to-end.

**CTA:** "Watch a live call in 5 minutes" → book demo.

---

## 3. Construction BOQ AI Estimator

**PROBLEM:** A BOQ (كراسة) takes days to price manually; suppliers change prices; margins and tax get hand-arithmetic'd.

**SOLUTION:** Upload PDF/drawings → extracted itemized BOQ → quantities, materials, labor, transport, supplier prices → tax + your margin → review → final quotation. Arabic first-class. Never fabricates a price — anything uncertain is **flagged for human review**.

**HOW IT WORKS**
1. Upload PDF / drawings.
2. Extract + classify every BOQ item.
3. Quantities → materials → labor → transport.
4. Supplier prices pulled from your stored history (missing → FLAG).
5. Apply your margin + tax → itemized quotation → review → export.

**DEMO (5 min):** upload sample BOQ PDF → extracted items table → costed items → grand total EGP → a flagged item routes to review → final quote PDF.

**FEATURES:** PDF/drawings input · BOQ item extraction · materials/labor/transport · supplier price memory · margin & tax · Arabic UI (RTL) · flag-for-review · historical prices · quote export.

**RESULT:** quotes in hours instead of days, priced from your real supplier history.

**PRICING**
| | STARTER | PRO | BUSINESS |
|---|---|---|---|
| Setup | $0 | $0 | $500 |
| Monthly | $99 | $299 | $799 |
| Quotes/mo | 10 | 50 | Unlimited |
| Supplier DB | no | 500 items | Unlimited |
| Arabic UI | yes | yes | yes + training |
| Flag-for-review | yes | yes | yes + manual override |
| Support | email | chat | dedicated |

**DONE-FOR-YOU:** $999 setup + $499/mo — we estimate your BOQs for you.

**CTA:** "Price your next BOQ in 10 minutes" → upload sample.

---

## 4. AI Lead Qualification Agent

**PROBLEM:** You bought a list of 10,000 "leads." 6,000 are dead numbers, duplicates, or placeholder garbage — and you only find out when your rep dials them.

**SOLUTION:** A qualification service that cleans and scores any list before you call: VERIFIED / CALLABLE / NOT CALLABLE / DUPLICATE / SUPPRESSED / NEEDS REVIEW, with reason codes.

**HOW IT WORKS**
1. Upload CSV (or connect API/CRM/form/lead engine).
2. Phone normalization + provenance + confidence checks run per record.
3. Each lead gets a status + reason code.
4. Export clean list or push straight to your dialer.

**DEMO (5 min):** upload CSV → results grid (VERIFIED/CALLABLE/DUPLICATE/SUPPRESSED/NEEDS REVIEW) → reason codes → export clean file.

**FEATURES:** phone normalization · provenance · confidence · reason codes · dedupe · suppression · NPI/registry proof · export · API endpoint.

**RESULT:** your reps only dial verified, callable, non-suppressed numbers.

**PRICING**
| | STARTER | PRO | AGENCY |
|---|---|---|---|
| Setup | $0 | $0 | $250 |
| Monthly | $49 | $149 | $499 |
| Leads/mo | 1,000 | 10,000 | 100,000 |
| API | no | yes | yes + SLA |
| Export | CSV | CSV+Excel | JSON+webhook |
| Support | email | chat | dedicated |

**DONE-FOR-YOU:** $499/setup — we clean your existing lists for you.

**CTA:** "Upload 1,000 leads, see results free" → try it.

---

## 5. AI Appointment Setter

**PROBLEM:** Missed calls = missed revenue. A receptionist costs $3k+/mo and can't be everywhere.

**SOLUTION:** An AI assistant that answers, qualifies, and books — on phone, website, WhatsApp, or form — then follows up, reschedules, cancels, and escalates to a human when needed.

**HOW IT WORKS**
1. Prospect contacts you (call/WhatsApp/web/form/CRM).
2. AI answers questions, qualifies, and identifies intent.
3. It collects details and books the appointment.
4. Lifecycle: follow-up → reschedule → cancel → escalate to human.

**DEMO (5 min):** dial number → Sarah the AI receptionist answers → asks service questions → books appointment in calendar → confirm → follow-up scheduled.

**FEATURES:** multi-channel intake · answer questions · qualify prospects · identify intent · collect details · book/reschedule/cancel · follow up · escalate to human.

**RESULT:** every call answered, every lead booked — 24/7, no receptionist salary.

**PRICING**
| | STARTER | PRO | BUSINESS |
|---|---|---|---|
| Setup | $0 | $0 | $500 |
| Monthly | $149 | $349 | $749 |
| Locations | 1 | 3 | Unlimited |
| Minutes | 500 | 2,000 | Unlimited |
| Channels | phone | phone+web+form | all (WhatsApp too) |
| Escalation | no | yes | yes + human handoff |
| Support | email | chat | dedicated |

**DONE-FOR-YOU:** $1,299 setup + $649/mo — we configure and run your assistant.

**CTA:** "Hear it book a real appointment" → call the demo line.

---

## Sales ladder (all products)
SERVICE → MANAGED SERVICE → PRODUCT → SAAS → WHITE LABEL
Every offer has a DFY tier so revenue starts before the full product is polished.