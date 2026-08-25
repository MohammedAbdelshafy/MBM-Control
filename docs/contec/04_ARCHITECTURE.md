# 04 — Architecture

Status: PROPOSED — platform-independent layering; platform binding pending decision
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## A1. Layered architecture

```
┌───────────────────────────────────────────────────────┐
│ UX layer: AR/EN, RTL/LTR, responsive web, fast entry  │
├───────────────────────────────────────────────────────┤
│ Contec custom-app layer (extensions ONLY):            │
│  OCR/AI pipeline · trust states · provenance views ·  │
│  bilingual helpers · import tools                     │
├───────────────────────────────────────────────────────┤
│ ERP platform core (UNSELECTED — see doc 03):          │
│  GL/AR/AP · projects/cost centers · inventory ·       │
│  assets · permissions · workflows · attachments       │
├───────────────────────────────────────────────────────┤
│ Runtime: Docker services + persistent volumes         │
│  (DB volume, files volume, TLS reverse proxy)         │
└───────────────────────────────────────────────────────┘
```

Policy: CONFIGURE → EXTEND → BUILD. The Contec layer must never modify core
accounting logic; it may only add entities, hooks, and UI around the platform's
sanctioned extension mechanisms. Any exception requires a written justification
in `DECISION_LOG.md` before implementation.

## A2. Source-provenance chain (MANDATORY)

Every important number shown to users must be traceable end-to-end:

```
DASHBOARD
   ↓ drill-down
REPORT
   ↓ built from
LEDGER (GL entries)
   ↓ posted by
TRANSACTION (invoice/bill/payment/JE/expense)
   ↑ derived from
SOURCE DOCUMENT
   ↑ evidenced by
ATTACHMENT / RECEIPT / INVOICE (file + metadata)
```

Implementation requirement: each dashboard/report figure must be able to answer
"which ledger entries compose you?" and each ledger entry "which source document
and attachment justify you?". AI-generated narrative may accompany figures but
must never replace or override the chain.

## A3. Trust-engine states

Canonical vocabulary for every extracted, suggested, imported, or displayed
value of consequence:

| State | Meaning | Set by |
|---|---|---|
| VERIFIED | Backed by verified ledger value or validated source record | System after validation/posting |
| UNVERIFIED | Plausible but not yet confirmed (incl. any AI suggestion until accepted AND validated) | System default for AI output |
| CONFLICT | Conflicting source records; no assertion allowed until resolved | Detection rules |
| NEEDS_REVIEW | Low-confidence OCR/extraction; mandatory human review queue | OCR pipeline |
| UNKNOWN | Missing information | Default |

Transition rules:

- MISSING → UNKNOWN. Never guessed.
- CONFLICT stays CONFLICT until a human resolves it with evidence.
- NEEDS_REVIEW cannot advance without human review.
- AI suggestion → UNVERIFIED even after acceptance; becomes VERIFIED only when
  bound to a validated ledger record.
- No display path may present UNVERIFIED values as final accounting fact.
- Downgrade rule: any edit to underlying evidence re-runs state evaluation.

## A4. AI safety boundaries

AI MAY: analyze, summarize, search, draft, classify, suggest, detect duplicates.
AI MAY NOT: post financial transactions, execute payments, submit taxes, change
permissions, delete records, alter posted transactions, or approve its own
suggestions. Model confidence scores are NOT evidence.

## A5. Integration architecture

- All programmatic access via the platform's official API with scoped,
  least-privilege tokens; read-only token class for AI retrieval.
- OCR provider abstracted behind an interface so the engine is replaceable;
  no hard dependency on one vendor/model (mirrors model-fallback doctrine).
- No direct database writes from external integrations; all writes go through
  platform workflows that enforce invariants.

## A6. Deployment shape (detail in doc 10)

Docker Compose baseline: app containers + database container with named volume
+ file-store volume + reverse proxy (TLS) + backup sidecar/schedule. Secrets via
environment only. Health checks per service. No DB port exposed publicly.

## Open items

1. Platform binding of every layer component. [PENDING DECISION]
2. Concrete extension mechanism per candidate (custom app vs module). [PENDING RESEARCH]
3. Search stack choice (platform-native first). [PROPOSAL: use native]
