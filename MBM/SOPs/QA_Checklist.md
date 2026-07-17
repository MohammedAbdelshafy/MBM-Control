# QA Checklist v1.1

## 1. Schema Validation
- [ ] Raw artifact has been mapped directly to `MBM/Templates/BAGA_Lead_Deliverable.csv`.
- [ ] No unauthorized columns exist in the final output.

## 2. Data Normalization
- [ ] Addresses have been cleaned using `normalize_address()` from `MBM/Scripts/reusable_parsers.py` (e.g., stripping punctuation, standardizing "Street" to "ST").
- [ ] Phone numbers have been cleaned using `clean_phone_number()`.

## 3. Deduplication (Zero Tolerance)
- [ ] Target dataset has been deduplicated against the normalized `Property_Address`.
- [ ] Target dataset has been cross-referenced against `MBM/Clients/[Client]/` to ensure the customer has not previously paid for this lead.

## 4. Confidence Threshold
- [ ] Every record possesses at least ONE explicit distress signal.
- [ ] Priority Tiers assigned (Tier 1 = Out of State + Distress, Tier 2 = Local Absentee + Distress).

## 5. Artifact Handoff
- [ ] Passed records written to `MBM/Clients/Internal/qualified_batch_[Date].csv`.
- [ ] KPI Tracker updated with Yield and Defect Rate.
