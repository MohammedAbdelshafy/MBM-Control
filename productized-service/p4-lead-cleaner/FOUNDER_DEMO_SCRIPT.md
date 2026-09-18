# Founder Demo Script — P4 Lead Cleaning DFY

**Target duration:** 5 minutes or less

## 1. Open the input

Show:

`productized-service/p4-lead-cleaner/demo/sample_lead_list.csv`

Say:

> “This is a labeled synthetic demo set. It is not customer data. I’m going to run the exact cleaner we use for the service.”

## 2. Run the existing cleaner

Run:

```bash
python productized-service/p4-lead-cleaner/clean_leads.py --demo
```

Do not edit the demo data.

## 3. Show the output

Open the generated:

- `demo/output/cleaned.csv`
- `demo/output/summary.json`
- `demo/output/report.md`

Point out that the runner produces a structured result rather than a hand-edited spreadsheet.

## 4. Explain the statuses

Show examples of:

- CALLABLE
- NOT CALLABLE
- DUPLICATE
- SUPPRESSED
- NEEDS REVIEW

Explain that each classification has a corresponding reason/status field.

## 5. Show duplicate handling

Point to the repeated phone number and the DUPLICATE result.

Explain:

> “The first instance is kept and later rows with the same normalized phone are marked duplicate.”

## 6. Show suppression handling

Point to the SUPPRESSED example.

Explain:

> “The existing suppression and quarantine indexes are applied before the final customer classification.”

## 7. Show the summary

Open `summary.json` and `report.md`.

Highlight:

- total records
- CALLABLE count
- NOT CALLABLE count
- DUPLICATE count
- SUPPRESSED count
- NEEDS REVIEW count
- reason breakdown

Do not quote invented performance percentages.

## 8. Explain the value

Use:

> “The point is not to promise that every record becomes a buyer. The point is to give your team a cleaner, reason-coded working list so they can spend their time on records that pass the pipeline and investigate the ones that do not.”

## 9. Present the offer

Say:

> “The DFY package is $499 for up to 10,000 rows, with a 48-hour target subject to the input and processing requirements. You send the list, we run the existing pipeline, QC the output, and return the cleaned CSV plus the summary and report.”

## 10. Ask for the commercial next step

Say:

> “Send me 1,000 rows and I’ll show you exactly what your list looks like after cleaning.”

### Demo rules

- Never present the synthetic demo as customer data.
- Never invent customer results.
- Never promise a specific callable percentage.
- Never claim a legal DNC guarantee beyond the actual suppression logic.
- Never contact the prospect from this script.
