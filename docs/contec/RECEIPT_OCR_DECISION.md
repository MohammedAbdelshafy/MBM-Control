# CONTEC RECEIPT OCR DECISION

**Role:** Contec ERP Research + Architecture Intelligence Agent
**Date:** 2026-08-26

Based on the quantitative benchmark data detailed in `RECEIPT_OCR_BENCHMARK.md`, this document formalizes the OCR and Document Intelligence architectural decision for Contec ERP.

## THE HARD TRUTH

Local, traditional open-source OCR engines (Tesseract, PaddleOCR) perform adequately on perfectly aligned, high-contrast, monolingual English templates. However, they fail critically when processing the unstructured, noisy, multi-lingual (Arabic/English), and crumpled documents common in Contec's construction field operations. 

**Any attempt to route raw OCR output directly to the General Ledger based on these engines is mathematically guaranteed to corrupt Contec's accounting.**

## WINNER: Multimodal LLM (VLLM)
**Recommendation:** Implement a provider-agnostic VLLM API (e.g., Gemini Flash, Claude Haiku, or a privately hosted equivalent) as the primary extraction engine.
- **Why:** It natively understands unstructured Arabic/English context, dynamically corrects for noise/rotation without brittle pre-processing, and reliably outputs JSON.

## FALLBACK: invoice2data
**Recommendation:** For known, high-volume digital vendor invoices (e.g., Sewedy Cables PDF invoices), bypass OCR entirely and use `invoice2data` for deterministic regex/template-based extraction.
- **Why:** 100% accuracy, zero cost, and immediate processing for structured digital PDFs.

## SPECIAL CASE: Unreadable Documents
If a document is completely cropped, illegible, or contains conflicting handwritten totals, the extraction layer must confidently fail and mark the record `NEEDS_REVIEW`. No guesses are allowed.

---

## CONTEC RECOMMENDATION & ARCHITECTURE

Contec will use a **Hybrid Strategy**: `invoice2data` for known PDFs + `VLLM Adapter` for unstructured photos/receipts. 
We will NOT lock into a single AI provider; the adapter must interface through a standard protocol that can map to any model.

### The Mandatory Contec Receipt Inbox Pipeline

To ensure absolute accounting safety, the following sequence is MANDATORY for all document processing:

```text
1. [UPLOAD] PHOTO / PDF
         ↓
2. [SECURE] PRIVATE STORAGE
         ↓
3. [HASH] SHA-256 (Immediate duplicate rejection)
         ↓
4. [EXTRACT] OCR / VLLM EXTRACTION (Vendor, Date, Subtotal, VAT, Total)
         ↓
5. [SCORE] FIELD CONFIDENCE
         ↓
6. [VALIDATE] VALIDATION RULES (Subtotal + VAT == Total)
         ↓
7. [CHECK] DUPLICATE SEMANTIC CHECK (Vendor + Date + Total match existing)
         ↓
8. [QUEUE] NEEDS_REVIEW (Draft State - Execution Paused)
         ↓
9. [HUMAN] HUMAN APPROVAL (UI shows Image + Extracted Fields side-by-side)
         ↓
10.[POST] ERPNext TRANSACTION (Purchase Invoice / Journal Entry)
```

**CRITICAL SAFEGUARD:** Step 10 cannot be reached automatically. The workflow explicitly enforces Step 9 (Human Approval) before financial posting.

## HUMAN REVIEW INTERFACE

The custom Frappe DocType (`Contec Receipt Inbox`) will feature a split-screen design:
- **LEFT PANE:** The raw original image/PDF document.
- **RIGHT PANE:** The extracted JSON fields, color-coded by confidence. The human operator reviews and amends the values directly in this pane before clicking `Submit to ERPNext`.
