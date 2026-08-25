# 08 — Arabic / English Specification

Status: ADOPTED PRINCIPLES (directive §13) + PROPOSED implementation details
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## B1. Non-negotiables

1. Arabic and English are first-class from day one — not a later skin.
2. One canonical data store. NO separate per-language databases or duplicate
   entity records per language.
3. No hard-coded English strings in UI code. No hard-coded Arabic strings.
   All UI text via the localization/i18n mechanism of the platform/custom app.
4. Full RTL and LTR layout support, switchable at runtime per user.

## B2. Data rules

- Entity records carry `*_ar` and `*_en` display fields (doc 05 D3); search
  matches both languages; mixed-language records are normal (e.g., English
  company name + Arabic customer name on one invoice).
- Canonical/reference keys (codes) are language-neutral.
- Reports print labels in UI locale but DATA values exactly as stored.

## B3. Layout & typography (PROPOSAL)

- `dir` attribute switches at document root; components must mirror
  (navigation, breadcrumbs, progress, tables' column order).
- Numbers remain Western digits in accounting displays by default
  [PROPOSAL — confirm with business]; dates formatted per locale.
- Fonts must include complete Arabic glyph coverage; test with real Egyptian
  business vocabulary, not lorem-ipsum.
- Mixed-direction text (Arabic sentence containing Latin codes/numbers) must
  render without bidi corruption in forms, lists, PDFs.

## B4. Required bilingual acceptance tests (map to doc 12)

1. Create customer/supplier/project with Arabic-only names → switch session to
   English → records intact, display falls back gracefully, data uncorrupted;
   switch back → identical.
2. Arabic notes + attachment metadata survive edit round-trips.
3. Validation messages appear in the active locale (never the other one).
4. RTL: forms, tables, dashboards usable with no clipped/overlapping text at
   360px mobile width AND desktop width.
5. Search finds a document typed in Arabic when its name is Arabic, and via
   its Latin code.
6. Exported PDF/report renders Arabic correctly (shaping, ligatures, RTL).

## Open items

1. Platform Arabic maturity check per candidate (community translations vs
   official; RTL quality). [bake-off scenarios 24–26]
2. Business confirmation on numerals policy. [PENDING DECISION]
3. Translation workflow for Contec custom strings (file format, review). [PROPOSED:
   standard i18n resource files reviewed like code]
