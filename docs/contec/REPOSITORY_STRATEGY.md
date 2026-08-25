# Contec ERP — Repository Strategy

Status: PROPOSAL — NOT APPROVED (awaits operator authorization; see D-010)
Owner: Terminal 2 recommendation
Last updated: 2026-08-25

## R1. Problem statement (evidence recap = blocker B4)

Current repository `MohammedAbdelshafy/base44-app`:

- ~600 MB history including committed build artifacts and binaries:
  `clipping-factory/frontend/.next/**` JS chunks/fonts, `public/demos/*.mp4`,
  `public/*.apk`, vendored `mbm-dialer/app/packages/**`.
- Observed operational impact (VERIFIED 2026-08-25): three full clone attempts
  failed mid-transfer (`fetch-pack: unexpected disconnect`, early EOF) even at
  `--depth 1`; only blob-filtered partial clone + sparse checkout succeeded.
  Any second terminal, CI runner, or backup job needing a full clone will hit
  the same wall.
- Content is an unrelated multi-product monorepo (Base44 app, MBM dialer,
  clipping factory). Contec currently shares only `docs/contec/`.

## R2. Recommendation

**Create a dedicated, clean `contec-erp` repository** for everything Contec
implementation-related. Reasons:

1. Clean history → fast reliable clones for all terminals/CI/servers.
2. Independent access control (financial system repo ≠ marketing repos).
3. No risk of accidental coupling to unrelated build pipelines (existing CI
   runs lint/typecheck/build of the Base44 app on every push — noise + risk).
4. ERP deploy servers should pull a minimal repo, not 600 MB of media.
5. Secret-scanning and audit scope stays small and financial-focused.

NO aggressive rewrite of the current repository and NO deletion of unrelated
files — the current repo remains untouched except `docs/contec/`.

## R3. Target structure (for the future repo — DO NOT create without authorization)

```text
contec-erp/
├── docs/                  # this doc set moves/copies here as source of truth
│   └── contec/
├── custom-app/            # Contec extension app for selected platform
├── deployment/
│   ├── docker-compose.yml
│   ├── env.example        # placeholders only
│   ├── reverse-proxy/
│   └── backups/           # scripts + restore runbook
├── infrastructure/        # server provisioning notes/scripts
├── tests/
│   ├── suites/            # per doc 12 T2
│   └── fixtures/          # seed dataset + control totals JSON
├── scripts/               # operational tooling
└── .github/workflows/     # secret scan + doc check + test gates (no secrets needed)
```

## R4. Interim rules while planning continues HERE

1. `docs/contec/**` is the only Contec-owned area in this repo.
2. Never add binaries/large assets under `docs/contec/`; diagrams as text
   (mermaid/ascii).
3. Branches prefixed `contec/…`; commits scoped to docs/tooling only (per M0/M1
   boundaries until new repo exists).
4. When the new repo is authorized: COPY (not move) `docs/contec/` there, keep
   a pointer note here, and continue implementation exclusively in `contec-erp`.

## R5. Decision request

Operator to approve: (a) create `contec-erp` repo under the same organization/
account; (b) confirm branch protection (no direct pushes to main; PR + review).
Until then, status stays PROPOSAL — NOT APPROVED (D-010).
