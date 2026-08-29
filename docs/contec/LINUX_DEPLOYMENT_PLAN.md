# CONTEC — LINUX DEPLOYMENT PLAN
# Future Migration Sequence: Windows Docker → Linux Server

**Status:** PLANNED (NOT EXECUTED) — Phase 0 Final Gate APPROVED 2026-08-29
**Date:** 2026-08-29
**Author:** Nemotron 3 Ultra / OpenCode
**Purpose:** Define the ordered, gated deployment sequence to run the Contec ERP runtime on a
Linux server (chosen in `LINUX_HOSTING_BAKEOFF_2026.md`) using official `frappe_docker`,
preserving the FROZEN architecture and M1 (S01–S17) with zero app-code changes.

**GOVERNANCE — HARD STOPS**
- This is a PLAN / RUNBOOK only. Nothing in it has been executed.
- Do NOT purchase the server. Do NOT provision the server. Do NOT deploy anything.
- Do NOT modify Windows Docker. Do NOT touch either Docker VHDX (`docker_data.vhdx`).
- Do NOT modify Contec application code.
- Every step is gated; owner approval is required before purchase, spend, or irreversible action.
- Windows Docker data (`docker_data.vhdx`, 103.8 GB) and Contec code remain UNTOUCHED.
- No vendor-core edits, no BOQ, EGP-only V1, Arabic+English first-class, AI/OCR suggestion-only.

**EVIDENCE CLASSIFICATION**
- **VERIFIED FACT:** checked against official source on 2026-08-29.
- **ESTIMATE:** derived / market figure varying by region/currency/VAT/term.
- **PROPOSAL:** recommended choice requiring owner approval.
- **UNKNOWN:** unknowable until provisioning / owner decision.

---

## 1. TARGET ARCHITECTURE (official frappe_docker, Phase 0 verified pins)

```
Hetzner CX33 — Ubuntu 24.04 LTS — region Falkenstein/Nuremberg [PROPOSAL; region subject to availability at provisioning — UNKNOWN]
└── Docker Engine (native Linux) [PROPOSAL]
    └── frappe_docker compose [VERIFIED FACT pins]
        ├── frontend    (nginx, port 80/443, HTTPS via Caddy/Traefik + Let's Encrypt)
        ├── backend     (erpnext v16.32.3) [VERIFIED FACT — base image frappe/erpnext:v16.32.3]
        ├── websocket   (socketio)
        ├── scheduler
        ├── queue-short / queue-long (workers)
        ├── db          (MariaDB 11.8) [VERIFIED FACT]
        ├── redis-cache / redis-queue (redis:6.2-alpine) [VERIFIED FACT]
        └── create-site + configurator (one-shot)
    + Frappe HR v16.16.0 [VERIFIED FACT — version-16 branch, 2026-08-07] + custom contec v0.1.0-m1 [VERIFIED FACT — apps/contec v0.1.0]
      (delivered via apps.json custom image build — pwd.yml alone ships only erpnext) [VERIFIED FACT]
Backups: provider snapshots (€0.012–0.0143/GB) [VERIFIED FACT] + Backblaze B2 via rclone (encrypted, off-site) [VERIFIED FACT $6.95/TB] + restore drill [GOVERNANCE: BACKUP IS NOT VALID UNTIL RESTORE-TESTED]
```

**Spec [VERIFIED FACT + PROPOSAL]:** **Hetzner Cloud CX33 — 4 vCPU / 8 GB RAM / 80 GB NVMe — €8.49/month** (net, ex-VAT, Falkenstein/Nuremberg; hetzner.com / docs.hetzner.com June 2026 adjustment; CX32 is deprecated → CX33 is its replacement) [VERIFIED FACT: price + deprecation].

**Version pins [VERIFIED FACT — Phase 0 Final Gate]:**
- **ERPNext: v16.32.3** (`frappe/erpnext:v16.32.3`). Why: exact image proven running on the host (M1_ENVIRONMENT addendum); do NOT use `v16.31.0` from local `pwd.yml` (stale, 2 patches behind) merely because the file says so; do not jump to v16.33.0 (2026-08-25, breaking change in CRM endpoint).
- **Frappe:** bundled `version-16` inside v16.32.3 image (Python ≥3.14 / Node ≥24 handled by official image).
- **HRMS: v16.16.0** (`version-16` branch). Why: matches M1 reference environment, mature (2026-08-07); v16.17.0 (2026-08-28) is fresh alternative.
- **Contec: v0.1.0-m1** (`apps/contec` = `0.1.0`).
- **frappe_docker tooling: v3.2.2** (pristine clone).

**Storage caveat [ESTIMATE + GOVERNANCE]: 80 GB is NOT universally sufficient.** It is adequate for ~10 users year-one provided backups stream off-box to B2, build layers are pruned after first build, and free space is monitored; heavy attachments, long on-box retention, or local restore staging may require scaling to CX43 (160 GB). See bake-off §2.

This target is **functionally identical** to the local `deployment/contec/frappe_docker` reference except the host is native Linux instead of Docker Desktop/WSL2 and the image pins are corrected to the Phase 0 verified set (local `pwd.yml` still pins `v16.31.0` [VERIFIED FACT] — that pin is superseded by this gate).
→ M1 S01–S17 execute without modification (per `M1_LINUX_RUNTIME_OPTIONS.md §12`) [PROPOSAL].

---

## 2. MIGRATION SEQUENCE (ordered, gated)

### PHASE 0 — Prerequisites (owner decision / approval gates) [GATED — OWNER APPROVAL REQUIRED]
- [ ] Buy **Hetzner CX33** (8 GB / 4 vCPU / 80 GB, **€8.49/month [VERIFIED FACT]**) — region **Falkenstein/Nuremberg, subject to actual availability at provisioning [UNKNOWN]** — Ubuntu 24.04 LTS [PROPOSAL].
- [ ] Register domain (e.g. `erp.contec.<tld>`, ~€10–15/yr) [UNKNOWN — TBD] [ESTIMATE].
- [ ] Create **Backblaze B2** bucket + app key (off-site backups) [PROPOSAL; B2 $6.95/TB [VERIFIED FACT]].
- [ ] Generate an SSH keypair; store the private key securely (do not commit to repo) [PROPOSAL].
- [ ] Confirm a restore drill schedule + retention policy (owner call) [UNKNOWN]. **GOVERNANCE: BACKUP IS NOT VALID UNTIL RESTORE-TESTED.**

### PHASE 1 — Server baseline [PROPOSAL]
- [ ] Hardening: SSH key-only, root login disabled, UFW (22/80/443 from admin IPs).
- [ ] unattended-upgrades, timezone, hostname, swap/ZRAM (small ZRAM swap helpful on 8 GB).
- [ ] Snapshot the fresh OS (baseline restore point, €0.012–0.0143/GB [VERIFIED FACT]).

### PHASE 2 — Docker Engine (native Linux) [PROPOSAL]
- [ ] Install Docker Engine from the official Docker apt repo (pin to a known version, e.g. 29.x).
- [ ] Verify: `docker run --rm hello-world`, `docker compose version`.
- [ ] Root-owned Docker socket; keep it off the public internet.

### PHASE 3 — Deploy frappe_docker [PROPOSAL; pins = VERIFIED FACT]
- [ ] Clone the existing pristine reference `deployment/contec/frappe_docker` (same repo, corrected pins) onto server.
- [ ] Configure `.env` from `deployment/contec/staging/.env` (admin password, DB passwords — never commit).
- [ ] Build the custom image via `apps.json` (**erpnext v16.32.3 + hrms v16.16.0 + contec v0.1.0-m1**) [VERIFIED FACT]. Use a GHA/CI build mirroring the pinned base so the Contec app is baked in (this is M1 S01). Local `pwd.yml` `v16.31.0` is superseded — do not copy it blindly.
- [ ] `docker compose up -d`; wait for `create-site`/configurator to complete.
- [ ] Health check: `docker ps`, site ping, `bench doctor`.

### PHASE 4 — Apps & site [VERIFIED FACT pins]
- [ ] Confirm **erpnext v16.32.3**, **Frappe HR v16.16.0**, **contec v0.1.0-m1** installed/listed in `sites/apps.txt` [VERIFIED FACT].
- [ ] `bench --site <site> install-app erpnext hrms contec` (idempotent).
- [ ] Configure EGP-only (currency = EGP, default country/company), enable Arabic (RTL) language pack, TOTP MFA,
      RBAC, private file storage. All configuration-level; no vendor-core edits.

### PHASE 5 — HTTPS & networking [PROPOSAL]
- [ ] Caddy/Traefik reverse proxy on port 443 with Let's Encrypt for the domain.
- [ ] Firewall: only 80/443 public; MariaDB/Redis internal-only.
- [ ] Enable 50 MB client body (already in frontend env) for file uploads; consider Cloudflare in front for DDoS only if desired.

### PHASE 6 — Backups & restore (S14/S15) [PROPOSAL + GOVERNANCE]
- [ ] Provider snapshot policy (daily/weekly, €0.012–0.0143/GB [VERIFIED FACT]).
- [ ] Scheduled `bench backup --with-files` → rclone (encrypted) → Backblaze B2 ($6.95/TB, first 10 GB free [VERIFIED FACT]).
- [ ] **Restore drill:** document and practice restoring DB + files + site from B2 to a fresh volume. **BACKUP IS NOT VALID UNTIL RESTORE-TESTED.**
- [ ] Hash-verify a restored archive (per backup-disaster-recovery skill).

### PHASE 7 — Execute M1 S01–S17 [PROPOSAL]
- [ ] Run the full `PLATFORM_BAKEOFF.md` bake-off scenarios against the live Linux stack.
- [ ] Record evidence per scenario; post-verify (read-only) before declaring M1 done.
- [ ] Update `M1_*` artifacts + `DECISION_LOG.md` with the deployment facts.

### PHASE 8 — Handover / operations [PROPOSAL]
- [ ] Write runbooks (backup, restore, scale-up, upgrade path, password rotation).
- [ ] Notify owner of final URL, admin credentials (delivered securely), and cost.
- [ ] Configure cost/budget alerts on Hetzner + B2.

---

## 3. ROLLBACK / CONTINGENCY

- **Before** any provider purchase: take OS snapshot; everything below steps out with no irreversible action.
- Accidental misconfig on the server → restore fresh OS snapshot, re-run phases.
- Provider outage → restore from B2 to a fresh **CX33** (documented restore runbook; ~30–60 min) [PROPOSAL]. If 80 GB proves tight, scale to **CX43 (160 GB, €15.99 [VERIFIED FACT])** [ESTIMATE].
- If Linux Docker were ever to fail: Option B/D in `M1_LINUX_RUNTIME_OPTIONS.md` remain as fallbacks
  (they do NOT touch the frozen app architecture).

---

## 4. WHAT IS DELIBERATELY UNCHANGED

- FROZEN architecture: ERPNext v16 + Frappe HR + custom `contec` app (no vendor-core edits) [VERIFIED FACT].
- **Corrected pins [VERIFIED FACT — Phase 0 Final Gate]:** `frappe/erpnext:v16.32.3` + `hrms v16.16.0` + `contec v0.1.0-m1` + `mariadb:11.8` + `redis:6.2-alpine` + `frappe_docker v3.2.2`. Local `pwd.yml` still reads `v16.31.0` [VERIFIED FACT] — superseded by this gate (do not use v16.31.0 merely because the file says so).
- **Host plan [VERIFIED FACT + PROPOSAL]:** Hetzner **CX33** (4 vCPU / 8 GB / 80 GB, **€8.49/month** [VERIFIED FACT]), Falkenstein/Nuremberg subject to availability [UNKNOWN].
- M1 S01–S17 scope and gates (PLATFORM_BAKEOFF.md) [VERIFIED FACT].
- Accounting integrity rules, EGP-only, Arabic+English, AI/OCR suggestion-only [VERIFIED FACT].
- Windows Docker data is preserved and untouched throughout [GOVERNANCE].
- No purchase, no provisioning, no deployment performed by this document [GOVERNANCE].

---

## 5. STATUS

```
CURRENT WINDOWS DOCKER: UNCHANGED (docker_data.vhdx intact, not touched) [VERIFIED FACT]
CONTEC CODE:            UNCHANGED [VERIFIED FACT]
M1 (S01-S17):           BLOCKED at S01 (Docker Desktop runtime corruption) — unblocks via this plan [VERIFIED FACT]
PHASE 0 GATE:           APPROVED 2026-08-29 — pins: erpnext v16.32.3 / hrms v16.16.0 / contec v0.1.0-m1 / CX33 €8.49 [VERIFIED FACT]
DEPLOYMENT:             NOT PERFORMED (planned only) [VERIFIED FACT]
HOST:                   Hetzner CX33 4v/8G/80G €8.49 — Falkenstein/Nuremberg subject to availability [VERIFIED FACT price / UNKNOWN availability]
PURCHASE AUTHORIZED:    NO [GOVERNANCE]
DEPLOYMENT AUTHORIZED:  NO [GOVERNANCE]
OWNER ACTION:           Approve purchase/spend + next single action (Phase 0) [PROPOSAL]
```

---

*Status: PLAN / RUNBOOK COMPLETE — Phase 0 harmonized 2026-08-29. No purchase, no provisioning, no deployment performed. No Windows Docker or VHDX touched. No Contec code modified. Awaiting owner authorization to execute Phase 0.*
