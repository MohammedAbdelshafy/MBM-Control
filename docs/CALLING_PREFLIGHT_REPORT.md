# Calling Preflight Report

**Generated:** 2026-08-29T20:54:08Z
**Mode:** READ-ONLY — no calls, SMS, or record mutations
**Input:** leads_database.json (4938 records) + npi_verified_callsheet.csv

## Count Reconciliation

| Stage | Count |
|---|---|
| RAW | 4938 |
| VALID (passes gate) | 938 |
| SUPPRESSED | 3500 |
| VERIFICATION_REQUIRED | 50 |
| ALREADY_CONTACTED | 450 |
| ACTIVE_DIALER | 938 |
| READY (callable) | 938 |
| BLOCKED | 4000 |
| Discrepancy | 0 |

## Breakdown by Status

| ACTIVE_DIALER | 938 |
| ALREADY_CONTACTED | 450 |
| SUPPRESSED | 3500 |
| VERIFICATION_REQUIRED | 50 |

## Pilot Batch (Top 20)

| # | Lead ID | Name | Company | Phone | Score | Segment |
|---|---|---|---|---|---|---|
| 1 | AI-BUYER-E3DCA62E | Dr. Sarah Lin | Premier Smile Partners Dental Group | +19726658140 | 84 | HEALTHCARE_CLINIC |
| 2 | AIC-AZ-2955BB | Mitchell Hayes | IntelliScale Machine Learning Advisors | +16028492011 | 82 | AI_CONSULTANCY |
| 3 | AIC-AZ-2B694B | Stuart Bennett | Verve Cognitive Technologies Consulting | +16028492010 | 82 | AI_CONSULTANCY |
| 4 | AIC-CA-177BDB | Franklin Ross | Zenith AI Strategy & Enterprise Architecture | +14158923013 | 82 | AI_CONSULTANCY |
| 5 | AIC-CA-7F4A7A | Elena Vasquez | Aura AI Consultancy & Algorithmic Solutions | +14158923012 | 82 | AI_CONSULTANCY |
| 6 | AIC-CA-8A47DE | Marcus Rothstein | Synapse Automation & Process Intelligence Inc | +14158923011 | 82 | AI_CONSULTANCY |
| 7 | AIC-CA-F71728 | Dr. Andrew Chen | Nexus Cognitive Systems & AI Engineering LLC | +14158923010 | 82 | AI_CONSULTANCY |
| 8 | AIC-CO-600AAD | Simon Bradley | Frontier AI Systems & Cognitive Cloud | +13038492011 | 82 | AI_CONSULTANCY |
| 9 | AIC-CO-F9EB1D | Victor Sanchez | Optima Intelligent Automation Group LLC | +13038492010 | 82 | AI_CONSULTANCY |
| 10 | AIC-FL-B2F92F | Dominic Price | AlphaCore AI Automation & Engineering Inc | +13058492010 | 82 | AI_CONSULTANCY |
| 11 | AIC-FL-C2E07B | Clarence Howard | Prism Neural Solutions & Advisory LLC | +13058492011 | 82 | AI_CONSULTANCY |
| 12 | AIC-GA-2382E9 | Nicholas Roy | Horizon AI Integration & Automation LLC | +14048492010 | 82 | AI_CONSULTANCY |
| 13 | AIC-GA-A4D6C0 | Albert Romero | InsightFlow Machine Learning Consultancies | +14048492011 | 82 | AI_CONSULTANCY |
| 14 | AIC-IL-00A016 | Warren Fletcher | Pinnacle AI Workflow Solutions Group | +13128492010 | 82 | AI_CONSULTANCY |
| 15 | AIC-IL-F09F7B | Felix Baumgartner | Cognitive Bridge Enterprise AI Advisors | +13128492011 | 82 | AI_CONSULTANCY |
| 16 | AIC-MA-26D0CD | Lawrence Vance | Summit Cognitive Advisory & Analytics Inc | +16178492011 | 82 | AI_CONSULTANCY |
| 17 | AIC-MA-712876 | Daniel Thorne | Kinetic AI Software Implementations LLC | +16178492010 | 82 | AI_CONSULTANCY |
| 18 | AIC-TX-31C0AF | Nathaniel Cross | VectorCraft Machine Learning Partners | +15129482102 | 82 | AI_CONSULTANCY |
| 19 | AIC-TX-4871E8 | Raymond Powell | Evergreen AI Process Automation Partners | +12149483103 | 82 | AI_CONSULTANCY |
| 20 | AIC-TX-545892 | Harrison Forde | Apex Cognition AI Consulting Group LLC | +17139482203 | 82 | AI_CONSULTANCY |

## Script Audit

- Segments found: HEALTHCARE_CLINIC, AI_CONSULTANCY, MOBILE_APPS, B2B_AGENCY, CONTRACTOR, WEBSITE_DESIGN, COMMERCIAL, SENIOR_OWNER
- Missing scripts: 0
- All segments supported: YES
- Playbooks generated: 5/5 sampled

## Timezone Validation

- UTC compliant: YES
- Non-UTC timestamps: 0

## Dialer Payload Validation

- All required fields present: YES

## Idempotency Check

- Unique phones: 4888
- Duplicate phones: 0
- Idempotent: YES

## Blocked Leads Summary

- Total blocked: 4000
  - SUPPRESSED_PHONE_INDEX: 3492
  - ALREADY_CONTACTED: 450
  - INVALID_PHONE:blank_phone: 50
  - SUPPRESSED_FLAG: 8

## Safety Checks

- No real calls placed: PASS
- No SMS sent: PASS
- No seller records mutated: PASS
- READ-ONLY mode: PASS

## Next Action

- Review 20 pilot leads in `calling_pilot_20.csv`
- Confirm CALLING_ENABLED=false remains set until human approval
- Manually dial the Prime 20 via telephonyProvider.js after approval
