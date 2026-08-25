# 08 — Arabic/English Specification

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decision: D-003
Principle: ONE canonical dataset; language is presentation only.

## 1. Language architecture

| Layer | Mechanism |
|---|---|
| UI chrome | Frappe translation system per user (`ar` / `en`), sourced from Crowdin + local CSV top-ups shipped in `contec` app (`contec/translations/ar.csv`) |
| Field labels/help | translations of doctype labels; custom fields get BOTH en+ar label via fixtures |
| Document data | bilingual master name fields: `*_en`, `*_ar` + canonical key (05 §2) |
| Print/PDF | two print formats per financial doc: `… EN` and `… AR`; Arabic format uses RTL stylesheet |
| Reports | script reports render column headers by user lang; exported XLSX includes both header languages |

No translated record tables, no second database, no locale-switching data forks.

## 2. Directionality (RTL/LTR)

- Desk sets `dir=rtl` for ar sessions (platform behavior); verify each custom
  page sets it explicitly — part of UI checklist (12 T-AR-3).
- Numbers, account codes, phone numbers stay LTR inside RTL text using
  Unicode bidi isolation where rendered by custom pages.
- Mixed rows (Arabic description with English SKU) must not scramble: test with
  sample "أسمنت OPC 50 كيس – P.O#123".

## 3. Data entry rules

- Keyboard-agnostic: OS-level Arabic keyboards; inputs never force LTR.
- Name fields accept either script; normalization utility (§7) powers search
  and duplicate detection in both scripts.
- Amount/date/currency inputs use Western digits (Egyptian business standard);
  display formatting may show Eastern digits ONLY in printed Arabic reports
  (config flag, default OFF).

## 4. Dates & currency

Gregorian calendar everywhere. Format `YYYY-MM-DD` internal; UI renders
locale-appropriate. EGP is the posting currency (D-016); FX fields exist but
V1 posts EGP-only.

## 5. Arabic search requirements

Search box on masters/transactions must match:
- exact substring in either script,
- normalized forms (أ إ آ→ا, ى→ي, ة→ه, ــ tatweel removal, diacritics strip),
- transposed script (typing "cement" finds "أسمنت" ONLY when a transliteration/
  alias mapping exists on the item — provided as optional `alias_en` field,
  NOT automatic machine translation).

## 6. Arabic name handling conventions

- Person names stored as typed (canonical) + en/ar renderings.
- Company names keep legal Arabic form in `_ar` and trade English in `_en`.
- Government entities (e.g., الحي / الجهاز) recorded in Arabic canonically;
  `_en` transliteration required for reporting.
- Duplicate guard compares normalized names across scripts via shared
  normalization output (09 §6).

## 7. Search normalization utility (`contec/utils/arabic_search.py`)

Single shared function used by: master search override, duplicate guard,
report filters. Steps: NFKC → strip harakat/tatweel → unify alef/yeh/teh
marbuta → lowercase latin → collapse spaces → strip punctuation. Unit-tested
with the golden string set in 12 §T-I18N.

## 8. Bilingual report/print matrix

| Document | AR print | EN print |
|---|---|---|
| Sales Invoice | ✔ (legal-facing) | ✔ |
| Purchase Invoice/bill register | ✔ | ✔ |
| Payment voucher/receipt | ✔ | ✔ |
| Project profitability | ✔ | ✔ |
| Trial balance/P&L/BS | ✔ | ✔ |
| Expense voucher (site) | ✔ primary | secondary |

Arabic PDFs must embed a proper Arabic font (Amiri/Noto Naskh Arabic bundled
in `contec` app assets) and pass the ligature/shaping smoke test (12 T-AR-4).

## 9. Acceptance summary

A user switching language sees fully localized chrome AND correct document
data rendering without data duplication; an Arabic-only storekeeper can operate
end-to-end; an English auditor can audit the same records end-to-end.
