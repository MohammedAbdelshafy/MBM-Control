# Revenue Offers — evidence-first contract

Implementation: `MBM/Offers/offer_schema.py`
Tests: `MBM/Offers/tests/test_offer_schema.py`

- Required: offer_id, problem, buyer_segment, promise, format, price,
  proof_assets, evidence_ids, evidence_level, limitations, checkout_rail,
  delivery_assets.
- Fabricated claims (market size, ROI, savings, traction, testimonials,
  revenue, guarantees) without `explicit_request`+ evidence are rejected
  with `FABRICATED_*` reason codes. Revenue/testimonial/guarantee claims
  require purchase-level evidence (`observed_purchase`+).
- Minimum end-to-end path: `validate_offer_end_to_end` (offer → conviction
  → QA). Proposal-only; consequential actions remain human-controlled
  via `lifecycle.can_publish`.
- Legacy `MBM/Offers/*.md` contain unsupported market/ROI/guarantee claims
  and FAIL validation (honest, not silently approved).
