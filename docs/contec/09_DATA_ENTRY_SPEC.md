# 09 — High-Volume Data Entry Specification

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-010, D-011
First-class requirement (R6). Every rule here is testable (12).

## 1. Entry profiles (who enters what, where)

| Profile | Primary docs | Device | Target time/doc |
|---|---|---|---|
| Site Engineer | Expense Voucher, Material Request, photo attach | Phone | ≤60s |
| Storekeeper | Stock Entry (receive/issue), counts | Tablet/phone | ≤45s/line |
| Accountant | Purchase/Sales Invoice, Payment Entry, claims, advances | Desktop | ≤3min invoice |
| Procurement | Purchase Order | Desktop | ≤4min |
| PM | approvals + expense vouchers | Phone/tablet | taps only |

## 2. Fast-entry form rules (all entry forms)

F1 Quick Entry: minimal mandatory set visible; everything else optional/advanced.
    Expense Voucher mandatory: amount, paid_to (free text allowed first pass),
    drawer, project→cost center default chain, photo.
F2 Defaults cascade: user → project → cost center → drawer/warehouse; sticky
    last-used values per user session.
F3 Numeric keypad (`inputmode=decimal`) on money fields; thousands separator
    live-format; no scientific notation ever.
F4 Enter-to-add-line on item grids; barcode/scan field on stock forms (camera
    scan acceptable).
F5 Save = single tap; draft auto-saved every 30s and on blur.
F6 Arabic-first labels for SITE/STORE roles (per-user language), English
    identical layout (no separate screens — 08 §1).

## 3. Draft → Submit state machine (universal)

```
DRAFT ──submit-permitted-role──▶ SUBMITTED ──cancel──▶ CANCELLED
  ▲                                │
  └──── amend (new draft lineage) ◀┘
```
- Only SUBMITTED documents hit the ledger. Drafts are working memory.
- State transitions validated server-side by Workflow (06 §3); client hints only.

## 4. Validation catalog (server-side, order fixed)

V1 Required-field presence (localized messages AR+EN).
V2 Amount > 0; quantity > 0; date within open period (07 §9); not future-dated
   beyond +1 day without reason code.
V3 Reference integrity: party active; project/cost center pair legal (05 §3);
   warehouse belongs to project warehouse group.
V4 Arithmetic recompute server-side (rates, VAT, WHT, totals) — never trust UI math.
V5 Duplicate detection (§6) → hard block or warn per class.
V6 Attachment policy (§7).
All violations return BOTH Arabic and English message keys (08).

## 5. Bulk import (Accountant+)

- Tool: Data Import (CSV/XLSX) for masters + opening balances; `contec` bulk
  API endpoint for transaction backfills with dry-run mode.
- Contract: file → row-level validation report (AR/EN columns) → commit only
  error-free rows or whole-file abort (user choice) → import manifest archived
  as Contec Document attachment.
- Import NEVER bypasses duplicate guard or workflow: imported transactions enter
  as drafts requiring the same submit authorization (R8).

## 6. Duplicate detection rules

| Class | Rule | Action |
|---|---|---|
| Supplier bill | (supplier, bill_no) unique among submitted+drafts | HARD BLOCK |
| Supplier near-dup | same supplier ±3d, |Δtotal|≤1% , similar normalized desc | WARN with side-by-side |
| Customer invoice | contract+period already billed flag | WARN |
| Payment double-fire | same party+amount+mode+account within 10 min | HARD BLOCK |
| Expense voucher | same user+amount+drawer ±1d + image sha256 match | HARD BLOCK |
| Master duplicates | normalized name similarity ≥0.92 | WARN at save |

Implementation: indexed prefilter query then scoring in `duplicate_guard.py`;
unit-tested (12). Blocking is data-class based, never role-based.

## 7. Attachments & OCR-ready pipeline (P7)

- Photo/PDF attach directly in entry form via camera capture (mobile) or drag.
- Policy (D-010): attachment REQUIRED before submit when grand_total ≥ EGP 1,000
  on Expense Voucher/Purchase Invoice (threshold fixture). No size bombs:
  max 15MB/file, images auto-downscaled to ≤1600px long edge client-side.
- Files land in PRIVATE files; `Contec Document` records sha256 for dedupe.
- Extraction fields (Phase 2): provider adapter writes `extraction_json`
  {vendor, date, total, currency, line_items[], confidence{field}}. UI shows
  side-by-side original vs extracted; reviewer confirms/corrects each field;
  confirmed values copy into the target draft. NOTHING posts from extraction
  without a human pressing Submit (D-011). Provider pluggable (vision-LLM
  preferred for mixed AR/EN receipts; Tesseract `ara+eng` fallback documented);
  no vendor lock in schema.

## 8. Search & retrieval under volume

List views default-filtered (current period + own scope) with saved filters;
global search hits canonical+normalized names (08 §5/§7); audit queries use
Access Log. Performance guardrail: any list >500 rows must be paginated —
enforced in custom pages, native lists already paginate.

## 9. Connectivity honesty (R6)

No offline mode in V1. Degradation strategy: lightweight pages, resumable
uploads (chunked), auto-save drafts, retry-on-flaky network for submits with
idempotency key (client-generated UUID stored on doc to make retries safe).
Paper fallback process documented for dead-zone sites: voucher book → batch
entry next online window → marked `late_entry` reason code (reportable).

## 10. Definition of done for any new entry screen

Passes 09 §2 F1–F6 checklist + validation catalog V1–V6 + AR/EN screenshots +
mobile viewport test + timing target met (12 T-DE-*).
