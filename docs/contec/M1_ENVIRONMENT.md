# M1 ENVIRONMENT — Verified Baseline (Contec ERP)

Status: HEALTHY · Recorded: 2026-08-26 · By: OX ALPHA
Purpose: immutable evidence baseline for M1 bake-off (PLATFORM_BAKEOFF.md S01–S17).
No secrets. Re-verify before go-live; this file records facts observed, not assumptions.

## Environment blocker resolution (2026-08-26)

| Item | Finding |
|---|---|
| Symptom | "Docker Linux engine unavailable" (npipe dockerDesktopLinuxEngine not found) — observed pre-recovery 2026-08-25/26 and on first launch attempt |
| Classification | **B — Docker Desktop started but Linux engine failed** (first Start-Process attempt died with its parent shell; second normal launch succeeded). NOT an architecture failure, NOT WSL failure, NOT damaged installation |
| Remedy applied | Normal Docker Desktop restart only (least-destructive step 5 of recovery order). No resets, no prunes, no volume deletion, no reinstall |
| Current verdict | **HEALTHY** |

## Verified live evidence (2026-08-26 ~11:44–11:52 +03:00)

| Check | Result |
|---|---|
| `docker version` | Client 29.6.1 + **SERVER Engine 29.6.1** (linux/amd64), Desktop 4.80.0, containerd v2.2.5, runc 1.3.6 |
| `docker info` | exit 0; 3.9s after idle wake (cold-start latency noted, see Risks); plugins buildx/ai/agent present |
| `docker context show` / `context ls` | **desktop-linux** active (intended Linux context); `default` present unused; no endpoint errors |
| Services | `com.docker.service` = Stopped/Manual — NORMAL for Desktop-on-WSL2 backend; engine runs in WSL distro |
| Processes | Docker Desktop running since 2026-08-26 00:41 local (stable ~11h at recording time) |
| `wsl --version` | WSL 2.7.8.0 · kernel 6.18.33.1-1 · WSLg 1.0.73.2 |
| `wsl -l -v` | `docker-desktop` Running v2 (only distro) |
| Install | `C:\Program Files\Docker\Docker\Docker Desktop.exe` present, 15,142,832 bytes, 2026-06-26 |
| Smoke test | `docker run --rm hello-world` → PASS (pull→create→run→stream; disposable, no persistent state) |
| Logs inspected (read-only, preserved) | `%LOCALAPPDATA%\Docker\log\host\docker-desktop.exe.log`: IPC activity 00:39–00:43 (launch) then quiet until diagnostics; no crash/error entries in tail. `%APPDATA%\Docker\reports.log`: hashed report IDs only. Install logs under `%ProgramData%\DockerDesktop` untouched |

## Host specification

| Item | Value |
|---|---|
| OS | Windows (build 10.0.26200.9168), PowerShell 5.1 |
| CPU | Intel Core i7-10510U @ 1.80GHz — 4 cores / 8 threads |
| RAM | 15.8 GB total |
| Disk C: | 923.8 GB used / **28.8 GB free** ⚠️ see Risks |
| Working copy | `C:\Users\omare\OneDrive\Desktop\AI` (OneDrive-synced — bind-mount risk, see Risks) |

## Target versions for M1 stack

| Component | Target | Source |
|---|---|---|
| ERPNext | **v16** (pwd.yml pins `frappe/erpnext:v16.31.0`) | frappe_docker@v3.2.2 + D-001 |
| Frappe | matching version-16 branch bundled in erpnext image | D-001 |
| Frappe HR (hrms) | version-16 — delivery path PENDING DECISION (custom apps.json image vs devcontainer get-app); pwd.yml does not ship it | PLATFORM_BAKEOFF §1, M1_INSTALL_LOG gap #1 |
| Custom app | `contec` skeleton, zero vendor edits | D-004 |
| Vendor tooling | frappe_docker @ tag **v3.2.2**, cloned to `deployment/contec/frappe_docker` (gitignored, pristine) | M1_INSTALL_LOG |

## Risks (logged, mitigations required before/during S01)

1. **Disk pressure**: 28.8 GB free. ERPNext v16 + MariaDB images ≈ 3–4 GB unpacked plus hrms/contec layers and site volumes. Mitigation: monitor `docker system df` after each S-step; do NOT prune autonomously (NO-DELETION rule) — report to operator if free space drops below ~10 GB.
2. **Cold-start latency**: first engine call after long idle took >45 s once (WSL VM wake). Mitigation: warm-up `docker info` before timed test steps in S-scenarios so slow calls don't masquerade as failures.
3. **OneDrive sync path**: never place bench sites/volumes or compose projects with bind mounts inside the synced folder; use Docker named volumes (pwd.yml already does).

## Honest status

```
M1 = PENDING EXECUTION
Environment = HEALTHY (blocker resolved via normal restart; evidence above)
Platform bake-off = NOT STARTED (S01–S17: 0/17 executed)
ERPNext functionality = UNTESTED — no claim made or implied by Docker health
```

## ADDENDUM 2026-08-26 (later same day) — PRIOR ENVIRONMENT DISCOVERED AND RECOVERED

The claim above that no ERPNext environment existed was **repo-true but host-false**:
the daemon was down during initial inspection, so running containers/volumes were
invisible. When the engine came up, a pre-existing stack auto-started. Corrected record:

| Fact | Evidence |
|---|---|
| Crashed session built an ERPNext stack at 2026-08-25 18:21 local (AFTER the 14:41 doc freeze) | container `Created=2026-08-25T15:21Z` (=18:21+03); compose project `contec`, config `repos\base44-app\deployment\compose\docker-compose.yml` (separate checkout; compose edited as late as 23:20) |
| Image | `frappe/erpnext:v16.32.3` stock official (4.03GB) — NOT a custom build |
| Site | `contec.local` created OK (`contec-create-site-1 Exited(0)`); configurator Exited(0); persistence via named volumes SURVIVED crash+engine-restart |
| Apps installed ON SITE | `['frappe','erpnext']` (bench console probe; Company DocType exists). HRMS/Contec never reached the env (`sites/apps.txt` has only frappe+erpnext) |
| Defect found | `contec-backend-1` existed state=Created, never started → frontend nginx crash-loop ×1699 (`host not found in upstream backend:8000`) |
| Recovery action taken | `docker start contec-backend-1` (minimal, reversible). Result: all 9 services Up; loop ended |
| Verification | `GET :8080/api/method/ping` → 200 `pong`; POST `/api/method/login` → 200 Logged In (Administrator, creds from their .env used in-memory only, not stored/committed); `frappe.auth.get_logged_user` → Administrator |
| Legacy preserved | Odoo-era experiment also present: `contec-odoo`+`contec-pg` Exited(255), volumes `contec_odoo_data` etc. — untouched, predates D-001 |
| Disk | free fell 28.8→13.1GB when engine materialized pre-existing data (WSL vhdx growth), then STABLE across 4 samples (13.09–13.12). Threshold rule (<10GB report) armed for upcoming build |

```
status: success
inputs: { trigger: "S01 directive", discovery: "prior contec stack" }
outputs: { addendum: "this section" }
errors: []
next_action: "deterministic custom-image S01 build as SEPARATE project (contecm1, port 8081); old stack preserved as baseline evidence"
owner: "system"
timestamp: "2026-08-26T12:40:00+03:00"
```

```
status: success
inputs: { directive: "docker-wsl diagnostic + environment record" }
outputs: { doc: "docs/contec/M1_ENVIRONMENT.md" }
errors: []
next_action: "decide hrms delivery path, then execute S01 run #1 verbatim"
owner: "system"
timestamp: "2026-08-26T11:55:00+03:00"
```
