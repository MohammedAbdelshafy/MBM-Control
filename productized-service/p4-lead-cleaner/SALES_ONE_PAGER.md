# P4 Lead Cleaning DFY

## Clean the list before your reps spend time dialing

Lead lists often contain duplicates, unusable phone numbers, missing verification, and records that need review.

P4 runs your list through an existing verification and classification pipeline and returns a reason-coded output so your team can see which records are callable, blocked, duplicated, suppressed, or need review.

## Who it is for

Agencies, wholesalers, real-estate teams, and other outbound teams working from purchased or internally sourced lead lists.

## What we do

For a supplied CSV or JSON lead list, P4:

- validates phone and name fields
- checks available verification evidence
- classifies records
- detects duplicate phones
- applies the existing suppression/quarantine indexes
- attaches reason codes and verification metadata
- produces a cleaned CSV plus summary artifacts

## What you send

A CSV or JSON lead list.

The current runner accepts common lead-field variants for names and phone numbers. Maximum commercial scope is **up to 10,000 rows per order**.

## What you receive

- `cleaned.csv`
- `summary.json`
- `report.md`

The cleaned output can classify records as:

- CALLABLE
- NOT CALLABLE
- DUPLICATE
- SUPPRESSED
- NEEDS REVIEW

The output also includes phone status, reason codes, verification source, and provenance-related fields produced by the pipeline.

## Delivery time

**48-hour target**, subject to input quality and processing requirements.

## Price

**$499 DFY** for up to 10,000 rows.

Pricing is an initial commercial test, not a claim about market-wide pricing.

## Scope

One lead-list cleanup job, up to 10,000 rows.

This is a data-cleaning and qualification service. It does not include outbound calling, prospect contact, campaign execution, or guaranteed contact rates.

## Limitations

Results depend on the evidence present in the supplied data and the verification sources available to the existing pipeline.

A record marked CALLABLE is a pipeline classification, not a guarantee that a person will answer or become a customer.

SUPPRESSED records should not be dialed. NEEDS REVIEW records require human review before use.

No fabricated customer results or testimonials are used.

## Proof

The repository contains a labeled synthetic demo dataset and reproducible output format. The demo is proof of pipeline behavior, not proof of customer results.

## Process

1. You send the lead list.
2. We validate and run the existing cleaner.
3. We review the generated output.
4. We deliver the cleaned CSV, report, and summary.

## FAQ

### Do you contact the leads?
No. This service cleans and classifies the list. Any outreach remains your responsibility.

### Can you guarantee a percentage of callable leads?
No. The result depends on the actual list and available evidence.

### Can I test a smaller sample?
Yes. A founder-controlled sample workflow can be discussed before the full job.

### What formats are supported?
CSV and JSON are supported by the current runner.

### What happens to suppressed records?
They are classified as SUPPRESSED by the existing suppression/quarantine logic and should not be dialed.

## CTA

**Send 1,000 rows for a sample review.**

See exactly how your list is classified, then decide whether the full **$499 / up to 10,000-row** cleanup makes sense.
