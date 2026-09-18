# P4 Lead Cleaning DFY — First Customer Offer

## Offer

**P4 AI Lead Cleaning DFY**

## Price

**$499**

This is the recommended initial commercial test price and is not market validation.

## Scope

Up to **10,000 rows** in a CSV or supported JSON input.

## Turnaround

**48-hour target**, subject to input quality and processing requirements.

## Includes

- `cleaned.csv`
- `summary.json`
- `report.md`

## Customer provides

A lead list in CSV or supported JSON format.

## Customer receives

- categorized leads
- CALLABLE / NOT CALLABLE / DUPLICATE / SUPPRESSED / NEEDS REVIEW classifications
- reason codes
- phone status
- verification-source fields
- duplicate and suppression results
- summary statistics
- human-readable report

## What is verified

The existing implementation visibly provides:

- phone validation
- name validation
- verification-source checks
- normalized-phone deduplication
- suppression/quarantine checks
- reason-coded classification
- reproducible output artifacts

The demo proves the output shape and processing path using synthetic test data.

## What is not verified

This repository evidence does not establish:

- a guaranteed callable percentage
- guaranteed successful contact or conversion
- a real customer outcome
- an automatically confirmed payment
- an automatically managed delivery portal
- automated outbound contact

Those claims must not be made.

## Customer responsibility

The customer remains responsible for:

- lawful use of their data
- determining whether and how they may contact records
- reviewing NEEDS REVIEW records
- complying with applicable calling, consent, privacy, and DNC requirements
- deciding what outreach action to take after delivery

P4 is a data-cleaning and qualification service, not legal advice or a guarantee of contactability.

## Simple process

1. Customer sends the list.
2. Founder receives and validates the input.
3. Existing P4 runner processes the file.
4. Founder performs QC.
5. Customer receives the three deliverables.

## Commercial next step

Start with a sample:

> **Send me 1,000 rows and I’ll show you exactly what your list looks like after cleaning.**

If the sample demonstrates useful value, the founder can propose the **$499 up-to-10,000-row DFY package**.
