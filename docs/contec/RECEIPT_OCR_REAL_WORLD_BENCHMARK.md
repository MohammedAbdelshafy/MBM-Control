# CONTEC RECEIPT OCR REAL-WORLD BENCHMARK PROTOCOL

**Role:** Contec ERP Research + Architecture Intelligence Agent
**Date:** 2026-08-26

## PURPOSE
This protocol defines the strict procedure for conducting a real-world OCR benchmark on actual Contec construction receipts and invoices.

> [!WARNING]
> DO NOT collect or upload real documents automatically. This document serves ONLY as the protocol. No real documents are to be processed until explicit organizational authorization is granted.

## 1. TARGET DATASET
- **Volume:** 50–100 manually selected, anonymized, and consent-authorized real documents.
- **Categories:**
  - Arabic printed receipts
  - English receipts
  - Arabic/English mixed receipts
  - VAT invoices
  - Supplier invoices
  - Expense receipts
  - Photographed documents (smartphone captures from the field)
  - PDF digital invoices
  - Edge cases: blurred, angled, cropped, crumpled, low-light, small text, long multi-page receipts, multi-line invoices.

## 2. GROUND TRUTH GENERATION (STRICT ISOLATION)
Ground truth data **must be generated independently** of any OCR system.

- **Mechanism:** A human operator will manually review each authorized document and transcribe the exact text into a JSON schema identical to the benchmark format.
- **Independence:** At no point can an OCR output be used to pre-fill or generate the ground truth JSON.
- **Required Fields:**
  - Vendor
  - Date
  - Document Number
  - Subtotal
  - VAT
  - Total
  - Payment Method
  - Currency
- **Optional/Contextual Fields:** Project, Cost Center.
  - *Note:* OCR must NOT be required to invent or infer Project/Cost Center. These fields are assigned strictly via Contec business logic and human review.

## 3. PRIVACY AND DATA PATH ENFORCEMENT
Every extraction mode must clearly define its processing perimeter:

- **LOCAL PATH:**
  - Tools like Tesseract or PaddleOCR process images 100% locally.
  - Privacy Risk: None.
  
- **EXTERNAL API PATH:**
  - Tools like Gemini VLLM or other cloud-hosted LLMs.
  - Required Logging: provider, data path, privacy risk, retention considerations.
  - **DPA Requirement:** Real Contec financial documents MUST NOT be transmitted to an external API unless a formal Data Processing Agreement (DPA) guaranteeing zero model retention/training is in place.

## 4. NEEDS_REVIEW TRIGGER CONDITIONS
The benchmark must rigorously test the system's ability to **fail safely**. Any of the following scenarios MUST force a `NEEDS_REVIEW` state and prevent automatic progression:

- Missing or `null` critical field
- Low confidence score
- Conflicting totals (Subtotal + VAT != Total)
- Unreadable or ambiguous vendor name
- Unreadable or missing date
- Duplicate candidate (Semantic or Hash match)
- Suspicious document number or amount

**Core Philosophy:** The system must prefer *"I cannot verify this"* over returning a plausible but incorrect value.

## 5. ACCOUNTING BOUNDARY
The exact boundary between AI and the General Ledger is immutable:

- **OCR/AI:** SUGGESTION ONLY
- **Human Operator:** VERIFICATION + ACCOUNTING CLASSIFICATION
- **ERPNext:** ACCOUNTING POSTING

This boundary must remain enforced server-side. AI must NEVER have the authority to trigger automatic payments or automatic ledger approvals.
