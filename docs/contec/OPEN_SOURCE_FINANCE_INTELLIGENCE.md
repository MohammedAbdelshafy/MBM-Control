# OPEN-SOURCE FINANCE INTELLIGENCE

**Role:** Contec ERP Research + Architecture Intelligence Agent
**Date:** 2026-08-26

## 1. Executive Summary
This intelligence mission evaluated top open-source finance, accounting, and OCR platforms to extract architectural patterns for the Contec ERP implementation. 
**FACT**: ERPNext remains the most suitable monolithic bedrock for construction accounting. 
**INFERENCE**: Contec does not need a new accounting engine; it needs a highly customized data-entry pipeline layered on top of Frappe that strictly enforces human verification. 
**PROPOSAL**: Adopt the receipt processing concepts from specialized pipelines (OCR -> structured JSON) while strictly mapping them into Frappe's Draft/Verify workflows to maintain absolute accounting integrity.

## 2. Repositories Investigated
- **ERPNext / Frappe** (Core bedrock)
- **dubbl** (Next.js/PostgreSQL accounting + OCR)
- **Akaunting** (Laravel accounting)
- **GnuCash** (C/Scheme double-entry personal finance)
- **Firefly III** (Personal finance manager)
- **bhimrazy/receipt-ocr** (Open-source OCR pipeline)
- **invoice2data** (Python template-based invoice extraction)
- **Receipt-Wrangler** (Open-source AI-driven receipt scanning pipeline)
- **keepr** (ledermann/keepr - Ruby bookkeeping gem. NOT a receipt pipeline).
- **docTR** (OCR engine)
- **PaddleOCR** (OCR engine)
- **Surya** (OCR and Layout Analysis engine)

## 3. License Matrix
| Repository | License | Copyright Implications | Commercial Use | Compatible? | Inspiration vs Reuse | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| ERPNext | GPLv3 | Strict copyleft | Yes | Yes (Core) | N/A | [GitHub](https://github.com/frappe/erpnext) |
| Frappe | MIT | Highly permissive | Yes | Yes (Core) | N/A | [GitHub](https://github.com/frappe/frappe) |
| dubbl | Apache 2.0 | Permissive, requires notice | Yes | Yes | Inspiration | [dubbl.dev](https://dubbl.dev/) |
| Akaunting | GPLv3 | Strict copyleft | Yes | No (PHP stack) | Inspiration | [akaunting.com](https://akaunting.com) |
| GnuCash | GPL | Strict copyleft | Yes | No (C/Scheme) | Inspiration | [gnucash.org](https://gnucash.org) |
| Firefly III | AGPLv3 | Highly strict copyleft | Yes | No (PHP stack) | Inspiration | [firefly-iii.org](https://firefly-iii.org) |
| invoice2data | MIT | Permissive | Yes | Yes | Code Reuse | [GitHub](https://github.com/invoice2data/invoice2data) |
| Surya | GPLv3 | Strict copyleft | Yes | No | Inspiration | [GitHub](https://github.com/vikp/surya) |

**UNKNOWN**: Whether dependencies within modern LLM-based OCR pipelines (like LLaVA or Qwen-VL) carry restrictive commercial usage licenses.

## 4. Accounting Capability Matrix
- **Double-entry ledger**: ERPNext (Yes), GnuCash (Yes), Akaunting (Yes), dubbl (Yes).
- **Chart of accounts**: ERPNext (Yes, mature), GnuCash (Yes, mature).
- **Journal entries, AR, AP, Payments, Receipts**: Supported universally across the major ERP/Accounting repos.
- **Bank reconciliation**: Firefly III (Strong API), ERPNext (Native).
- **Financial periods, Closing, Reversals, Audit trails**: ERPNext (Mature, strict immutable ledgers), GnuCash (Mature).

**INFERENCE**: ERPNext natively handles all complex accounting requirements matching or exceeding other open-source tools.
**PROPOSAL**: Do not attempt to replicate or replace any accounting ledger logic. Rely entirely on ERPNext's `GL Entry` controller.

## 5. Project Accounting Findings
**FACT**: ERPNext natively integrates Projects with Cost Centers and General Ledger tracking. 
**FACT**: Personal finance tools (Firefly III, GnuCash) lack robust multi-dimensional project accounting.
**PROPOSAL**: Enforce the `Project -> Cost Center -> Expense -> Invoice -> Payment -> Revenue` model exclusively using native Frappe DocTypes.

## 6. Receipt/OCR Findings
**FACT**: Classical OCR engines (Tesseract) struggle with noisy, complex Arabic layouts.
**FACT**: Surya OCR excels at layout detection for Arabic but requires significant compute.
**FACT**: Native docTR models fail on Arabic without custom weights.
**INFERENCE**: No local OCR engine will hit >90% accuracy on crumpled Arabic receipts out-of-the-box without extensive fine-tuning. Multimodal VLLMs (GPT-4o/Gemini) currently offer superior zero-shot performance on complex noisy receipts.
**PROPOSAL**: Adopt a modular pipeline where the OCR engine (Local or VLLM) outputs to a Draft, but AI output MUST NEVER post financial entries directly.

## 7. Data Entry Findings (High-Volume)
**FACT**: High-speed accounting requires keyboard-friendly interfaces (GnuCash register style).
**INFERENCE**: Standard web grid forms are slow for bulk entry.
**PROPOSAL**: Build custom Frappe Client Scripts implementing aggressive auto-focus, enter-to-submit, and default values to match native desktop speeds. Use Frappe's `Data Import` tool for bulk operations.

## 8. Import Findings
**FACT**: ERPNext has a robust native Data Import tool supporting CSV/Excel, dry runs, and rollback.
**PROPOSAL**: Reject building custom import parsers. Use Frappe's Data Import engine for all bulk data migrations and daily spreadsheet uploads.

## 9. Reconciliation Findings
**FACT**: Bank reconciliation is solved elegantly by rule-based matchers (Firefly III API).
**INFERENCE**: ERPNext's Bank Reconciliation Tool has matching rules but requires strict configuration.
**PROPOSAL**: Extend ERPNext's Bank Reconciliation Tool with tighter exact-amount matching rules tailored to EGP construction cashflows.

## 10. Security Findings
**FACT**: Akaunting and Firefly III enforce strict segregation of duties.
**PROPOSAL**: Adopt strict server-side validation in Frappe: creator ≠ approver for financial documents.
**UNKNOWN**: Whether the current deployment infrastructure handles secrets securely outside of `site_config.json`.

## 11. RBAC Findings
**FACT**: Frappe has an incredibly mature Role-Based Access Control system (Role Profiles, User Permissions).
**PROPOSAL**: Rely entirely on native Frappe RBAC. Do not invent custom permission tables.

## 12. Arabic/English Research (RTL)
**FACT**: "Supports Unicode" does not equal "Good Arabic UX".
**FACT**: Frappe natively supports proper RTL CSS flipping (`frappe-rtl`).
**INFERENCE**: No external layout libraries are needed for RTL.
**PROPOSAL**: Ensure all custom print formats and UI components in the `contec` app use Frappe's `_()` translation wrapper. Normalize Arabic searches (e.g. converting ة to ه during search queries) at the database/query layer.

## 13. Construction-Specific Findings
**FACT**: We do NOT need BOQ.
**PROPOSAL**: Investigate only the Project -> Contract -> Revenue -> Expense -> Procurement -> Inventory -> Subcontractor -> Payment -> Project Profitability flow natively within ERPNext. Do not build estimating modules.

## 14. Egypt-Specific Findings
**FACT**: Generic open-source tools do not natively support ETA e-invoicing out-of-the-box without localization apps.
**INFERENCE**: EGP handling and basic VAT are natively supported by ERPNext's generic tax engine.
**PROPOSAL**: Configure ERPNext's `Taxes and Charges Template` for Egyptian VAT and withholding tax. 
**UNKNOWN**: Whether local Egyptian tax reporting requires specific CSV export formats that must be custom-built.

## 15. Backup/Restore Findings
**FACT**: Mature deployments use automated cron jobs pushing to S3-compatible storage.
**PROPOSAL**: Rely on `frappe_docker`'s volume management and `bench backup` scripts, ensuring backups include database, configuration, and files.

## 16. Accounting Control Research
**FACT**: The best repositories (like GnuCash) enforce immutable posted records and exhaustive tests for negative balances and reversals.
**INFERENCE**: Contec must adopt this defensive testing posture.
**PROPOSAL**: Write Frappe `frappe.tests` that intentionally attempt to save unbalanced GL entries. Enforce rules where cancellations spawn explicit reversal GL entries, never deletions.

## 17. Recommended Contec Features
- **Contec Receipt Intelligence Architecture**: 
  `PHOTO/PDF` -> `PRIVATE FILE STORE` -> `SHA256 (Duplicate Prefilter)` -> `OCR` -> `FIELD EXTRACTION (Vendor, Date, Amount, VAT)` -> `CONFIDENCE SCORE` -> `VALIDATION RULES` -> `DUPLICATE CHECK` -> `NEEDS_REVIEW (Draft)` -> `HUMAN APPROVAL` -> `ERPNext TRANSACTION (Purchase Invoice / Journal Entry)` -> `GL` -> `PROJECT` -> `COST CENTER` -> `REPORT`.
- **Defensive Reversals**: Ensure cancellations spawn explicit reversal GL entries, never deletions.
- **Strict Project Allocation**: Mandatory Cost Center linking on all expense documents.

## 18. Features We Should NOT Build
- Bill of Quantities (BOQ).
- A custom accounting ledger or Double-Entry engine.
- A standalone mobile app (rely on Frappe's mobile-responsive PWA).
- Automated AI posting (strict violation of trust rules).

## 19. Code-Reuse Candidates
- `invoice2data` (Python): For deterministic template-based extraction of known supplier invoices.
- `pytesseract` (Python): For raw OCR text extraction within Frappe background jobs (when documents are clean).

## 20. Architecture-Inspiration Candidates
- **dubbl**: For its modern API-first approach to receipt handling.
- **GnuCash**: For its unyielding strictness regarding double-entry invariants and transaction register UX.

## 21. License Risks
- **FACT**: Pulling GPL/AGPL code (Firefly III, Akaunting, Surya) directly into a proprietary or internal system can trigger viral open-source requirements if distributed.
- **PROPOSAL**: Strictly avoid copying code from AGPL/GPL repositories. Limit reuse to MIT/Apache 2.0 libraries (like `invoice2data`). Use GPL tools (like Surya) via isolated containerized API endpoints rather than direct code import.

## 22. Recommended Implementation Order
1. **Foundation**: Configure native ERPNext Chart of Accounts, Projects, and Cost Centers.
2. **Security & Roles**: Implement RBAC and Creator ≠ Approver workflows.
3. **Receipt Pipeline**: Build the `Contec Receipt Inbox` DocType.
4. **OCR Integration**: Integrate extraction engine outputting to the Inbox.
5. **Testing**: Write reconciliation and negative balance tests.

## 23. Unknowns
- **UNKNOWN**: The exact accuracy of `pytesseract` vs. Surya vs. VLLMs on poor-quality, mixed Arabic-English, crumpled Egyptian receipts in field conditions.
- **UNKNOWN**: Whether Frappe's native mobile PWA is fast enough for field crews taking receipt photos, or if a lightweight Telegram bot integration is better.

## 24. Evidence / Source Links
- [ERPNext GitHub](https://github.com/frappe/erpnext)
- [GnuCash](https://gnucash.org/)
- [Firefly III Docs](https://docs.firefly-iii.org/)
- [invoice2data GitHub](https://github.com/invoice2data/invoice2data)
- [dubbl GitHub](https://github.com/dubbl-org/dubbl)
- [Surya GitHub](https://github.com/vikp/surya)
- [docTR GitHub](https://github.com/mindee/doctr)

---
# FINAL RANKING

### TIER 1: STRONGLY RECOMMENDED
1. **Contec Receipt Inbox (Human-Verified Pipeline)**
   - **VALUE**: High (solves data entry bottleneck)
   - **EFFORT**: Medium (Frappe DocType + Workflow)
   - **RISK**: Low (isolated from core GL until verified)
   - **LICENSE RISK**: None (built from scratch in Frappe)
   - **ACCOUNTING RISK**: Low (requires human verification)
   - **SECURITY RISK**: Low
   - **CONTEC FIT**: Perfect
   - **DEPENDENCIES**: Frappe native
   - **TEST REQUIREMENTS**: Unit tests for Draft -> Submitted transitions.

### TIER 2: USEFUL ENHANCEMENTS
1. **VLLM / High-Confidence OCR Extraction**
   - **VALUE**: High (automation)
   - **EFFORT**: High (tuning for Egyptian receipts)
   - **RISK**: Medium (OCR hallucinations)
   - **LICENSE RISK**: Low (API usage)
   - **ACCOUNTING RISK**: Low (outputs to DRAFT state only)
   - **SECURITY RISK**: Low
   - **CONTEC FIT**: High
   - **DEPENDENCIES**: Python API libraries
   - **TEST REQUIREMENTS**: Mocked API responses to test correct field mapping.

### TIER 3: LATER
1. **Telegram Bot for Field Receipt Capture**
   - **VALUE**: Medium (convenience)
   - **EFFORT**: Medium
   - **RISK**: Low
   - **LICENSE RISK**: None
   - **ACCOUNTING RISK**: Low
   - **SECURITY RISK**: Medium (requires webhook authentication)
   - **CONTEC FIT**: Addresses the "Unknown" regarding PWA field performance.
   - **DEPENDENCIES**: Telegram API

### REJECT: Not appropriate for Contec
1. **Bill of Quantities (BOQ)**
   - **REASON**: Explicitly excluded from V1.
2. **Autonomous AI Posting**
   - **REASON**: Violates core trust rules (`UNKNOWN ≠ GUESS`).
3. **Alternative Accounting Engines (GnuCash/Akaunting core)**
   - **REASON**: ERPNext core is already mature and replacing it violates the frozen architecture rule.
