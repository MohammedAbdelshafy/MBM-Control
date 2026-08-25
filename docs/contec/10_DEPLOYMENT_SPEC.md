# 10 — Deployment Specification

Status: PROPOSED — target environment UNDECIDED; no production deployment performed in M0
Owner: Terminal 2 (deployment safety) / Terminal 3 (implementation later)
Last updated: 2026-08-25

## Y1. Required shape (any target)

- Docker-based, reproducible from committed compose + env template.
- Persistent named volumes: database data AND attachment/file store. No data
  inside container layers.
- HTTPS at the edge via reverse proxy; app behind it only.
- All configuration/secrets via environment variables; `.env` git-ignored;
  committed template contains placeholders ONLY.
- Health check endpoint per service; logging to persistent/joined location;
  basic monitoring (uptime + disk + backup freshness).
- Database ports NEVER exposed publicly.

## Y2. Environment variables template (placeholders only)

```ini
# contec deployment — fill on server; NEVER commit real values
CONTEC_DB_HOST=db
CONTEC_DB_PORT=5432
CONTEC_DB_NAME=contec
CONTEC_DB_USER=contec_app
CONTEC_DB_PASSWORD=CHANGE_ME_STRONG
CONTEC_FILES_VOLUME=contec_files
CONTEC_BACKUP_DIR=/backups
CONTEC_BACKUP_SCHEDULE=0 2 * * *
CONTEC_BACKUP_RETENTION_DAYS=30
CONTEC_OFFSITE_TARGET=            # rclone/S3-compatible remote, optional but recommended
CONTEC_SITE_URL=https://contec.example
TLS_EMAIL=admin@example.com
```

(Platform-specific vars like DB engine/admin accounts are added after doc 03
decision; this template is the minimum contract.)

## Y3. Target options — evidence rules

| Option | Status | Evidence required before choosing |
|---|---|---|
| Existing Contec server/PC | CANDIDATE | hardware inventory, uptime reality (electricity/internet), who reboots it, disk for 90-day backup window |
| Genuinely free cloud | CANDIDATE | CURRENT limits page citations (RAM/CPU/storage/bandwidth), persistence guarantees, account requirements; "free forever" claims NOT accepted without the provider's own terms |
| Low-cost VPS fallback | FALLBACK | cheapest viable spec quote meeting platform requirements + backups |

No option is selected on assumption. Selection recorded in DECISION_LOG with
citations. [PENDING DECISION]

## Y4. Backup design (all three classes)

1. **Database**: nightly scheduled dump + pre-change manual dumps; retention
   ≥ 30 days local.
2. **Attachments/files**: nightly sync of files volume.
3. **Configuration**: compose files, env template (NOT real env), reverse-proxy
   config, restore runbook itself.

Off-site encrypted copy where practical (Y2 `CONTEC_OFFSITE_TARGET`).

**Restore drill (mandatory before any GO):**

```
1. take fresh backup on staging
2. wipe a clean environment
3. restore DB + files + config
4. boot stack → health checks green
5. login as test user works
6. verify accounting: trial balance zero; open one invoice+bill+payment and
   confirm amounts match pre-backup control sheet
7. verify attachments open; users exist; reports render
8. record drill result (date, executor, timings, issues) in release notes
```

A backup that has never passed this drill is NOT considered valid.

## Y5. Rollback

Every deployment change ships with: previous image/version tag, restore point,
and documented one-page rollback steps. Production changes require a fresh
backup immediately before change (OX_ALPHA shared rule #10).

## Open items

1. Target selection per Y3. [PENDING DECISION]
2. Platform official Docker images vs community — verify per candidate. [bake-off]
3. Monitoring stack choice (keep minimal: uptime + disk + backup-age). [PROPOSED]
