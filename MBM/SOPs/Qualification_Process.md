# Qualification Process

## Objective
To filter raw leads down to a refined list of highly motivated sellers with verifiable contact information, eliminating duds and dead-ends.

## Process

**1. Ingestion**
- Load the raw dataset from `MBM/Artifacts/raw_leads_...csv`.

**2. Deduplication & Cleanup**
- Remove any duplicate property addresses or owner names.
- Standardize address formatting and phone number structures.

**3. Motivation Verification**
- Cross-reference the primary motivation signal (e.g., if Tax Default is the criteria, confirm the data column holds a valid date/amount).
- Discard any records missing the critical motivation signal.

**4. Contact Verification**
- Cross-reference owner names with skip-tracing APIs or available databases to secure at least one verified phone number or email address.
- **Strict Rule:** If a property owner cannot be mapped to a verifiable contact method, move the record to `MBM/ParkingLot/` for future deep-skip-tracing. Do not include it in the active batch.

**5. Artifact Generation**
- Save the refined, qualified dataset to `MBM/Artifacts/qualified_leads_[YYYY-MM-DD]_[CampaignName].csv`.
