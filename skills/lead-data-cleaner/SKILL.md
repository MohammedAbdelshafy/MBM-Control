---
name: lead-data-cleaner
description: Clean and quality-check a customer-authorized CSV or JSON dataset. Use for normalization, deduplication, field QA, exclusion reasons, or a reproducible before/after report.
---
# Lead Data Cleaner
1. Confirm the input is customer-provided or otherwise authorized.
2. Inspect headers, row count, null rates, and format inconsistencies.
3. Preserve raw input separately; never silently overwrite source data.
4. Normalize whitespace, casing, phone formatting, and field labels only when deterministic.
5. Deduplicate using stable keys. Prefer normalized email; otherwise use an explicit fallback key such as name + company and report the rule.
6. Classify every exclusion with a reason.
7. Flag questionable values rather than presenting them as verified.
8. Reconcile input, kept, excluded, and duplicate counts.
9. Deliver cleaned data, QA summary, rules, and limitations.
Guardrails: never invent contact details, seller intent, consent, deliverability, or legal contactability. Syntax checks are not verification.
