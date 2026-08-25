# 02 — Process Map

Status: PROPOSED — derived from mission scope; NOT business-approved
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

Processes below are reconstructed from the V1 scope of
`docs/CONTEC_ERP_AGENT_MISSION.md`. They define WHAT must work; HOW depends on
the selected platform (CONFIGURE → EXTEND → BUILD). Terminal 1 must validate
with the business before implementation.

## P1 — Project lifecycle

```
Project created
→ Contract (simple) + budget
→ Cost centers attached
→ Revenue (customer invoices) + Costs (bills, expenses, issues, subcontractor bills)
→ Project profitability report
→ Closure
```

Invariants: every project cost/revenue line carries project + cost-center
dimensions where applicable; profitability = revenue − attributable costs,
traceable to ledger (see provenance chain, doc 04).

## P2 — Order-to-cash

```
Customer → Sales invoice (AR) → Receipt(s) against invoice → AR aging
```

Rules: partial payments allowed; receipt never exceeds outstanding unless a
documented advance policy exists (PENDING DECISION); posting only through the
platform's native AR workflow.

## P3 — Procure-to-pay

```
Supplier → Purchase (optional PO) → Supplier bill (AP)
→ Supplier payment → AP aging
Material receipt → warehouse or direct-to-site store
Issue to project → project cost
```

## P4 — Employee advance & settlement

```
Advance request → approval → payment (employee becomes debtor)
→ expense receipts submitted → settlement entry
→ remaining cash returned OR converted to expense
```

No settlement may leave a residual unexplained balance.

## P5 — Receipt / OCR pipeline (AI-safe)

```
Receipt image/PDF → upload (attachment bound to draft document)
→ OCR extraction → field confidence scores
→ NEEDS_REVIEW if low confidence (mandatory human review queue)
→ suggestions: account / project / cost center / tax / party
→ human accepts/edits each suggestion (accepted ⇒ UNVERIFIED until saved+validated)
→ submit → approval → POST via native accounting workflow
```

Hard rules: OCR/AI never posts autonomously; an explicit REVIEW state is
mandatory; confidence scores stored with the extracted data.

## P6 — Month-end / period close

```
Reconciliations (bank, cash, AR/AP control vs subledger)
→ accruals/corrections via journal entries
→ trial balance zero-check → period close → reports frozen
```

Period-close mechanics are platform-dependent: PROPOSED, verify per candidate
in bake-off scenarios 18–21.

## P7 — Corrections

```
Error discovered on POSTED document
→ reversal or correction entry (never silent edit)
→ link correction ↔ original for audit trail
Draft documents may be edited/deleted freely by their owner pre-submission.
```

## P8 — Document lifecycle (attachments)

```
Upload → attach to transaction/draft → VERIFIED when bound to posted ledger record
Archive (revoke visibility) → retention policy
→ controlled administrative deletion ONLY if legally appropriate (audited)
```

## Open items (Terminal 1)

1. Approve/adjust P1–P8 with the business. [PENDING DECISION]
2. Define subcontractor billing flow detail (retention/withholding?). [PENDING RESEARCH]
3. Define site-store transfer flow between warehouses. [PROPOSED]
4. Asset purchase → capitalization → depreciation → maintenance flow mapping. [PROPOSED]
