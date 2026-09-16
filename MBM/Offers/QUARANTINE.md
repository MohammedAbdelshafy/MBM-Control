# Legacy offers — QUARANTINED AS DRAFT

Status: `01_ShortForm_Content_Engine.md`, `02_AI_Lead_Gen_Engine.md`,
`03_Email_Followup_Automation.md` are **DRAFT-QUARANTINED**.

Evidence: `MBM/Offers/tests/test_offer_schema.py::test_legacy_offer_fails`
proves legacy-style claims (`$2.74B market`, `78%`, ROI/savings,
`money-back guarantee`, `$497/mo` pricing) FAIL `offer_schema.validate_offer`
with `FABRICATED_MARKET_DATA` / `FABRICATED_GUARANTEE` / related codes
when evidence is absent.

Path to release: REWRITE THROUGH OFFER SCHEMA
(`MBM/Offers/offer_schema.py` + `EVIDENCE_CONTRACT.md`) with real
proof_assets, evidence_ids, purchase-level evidence for revenue/guarantee
claims, limitations, checkout_rail, and delivery_assets — then pass
`validate_offer_end_to_end` and `lifecycle.can_publish` (ARMED + approval).

No legacy markdown offer may be published, charged, or sent until it passes.
