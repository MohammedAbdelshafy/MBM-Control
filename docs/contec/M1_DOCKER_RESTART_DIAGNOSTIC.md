# CONTEC M1 — DOCKER RESTART DIAGNOSTIC

**Mode:** READ-ONLY FORENSIC + DECISION. No destructive action executed.
**Date:** 2026-08-27 (restart after OpenCode crash). **Agent:** HY3
**OXYGEN RULE:** triggered (no ≥110 GB backup destination + runtime rebuild is destructive) → STOP, DOCUMENT, ESCALATE.

---

## CURRENT STATE
repository: `MohammedAbdelshafy/base44-app` (working copy `C:\Users\omare\OneDrive\Desktop\AI`)
branch: `master`
HEAD: `9f274a6` (feat: P0 Hardening — DNC enforcement…)
uncommitted: many unrelated MBM/clipping/real-estate files modified + untracked agent skills; **no Contec/Docker destructive change made this run**.
latest Contec-related commit: `46b87f1` refactor(contec): isolate receipt OCR benchmark tooling (no live Contec stack change).

## WSL
status: **DEGRADED / UNRESPONSIVE** — `wsl --status`, `wsl --version`, `wsl -l -v` all HANG (no output within 60s timeout). NEW vs prior docs (which reported them working).
version: reported by prior docs as WSL 2.7.8.0 (NOT re-verifiable this run because `wsl` CLI hangs).
docker-desktop: single registered distro; registry BasePath = `\\?\C:\Users\omare\AppData\Local\Docker\wsl\main`. Prior docs: STATE Stopped. NOT re-verifiable this run.

## DOCKER
cli: `docker.exe` (Docker Inc, 29.6.1) resolves to legit path `C:\Program Files\Docker\Docker\resources\bin\docker.exe`. HANGS on `--version` / `context ls` / `version` / `info` / `ps` (no output within 90s).
backend: processes ALIVE — `com.docker.backend` (×2), `com.docker.build`, `Docker Desktop` (×5), `docker-agent`, `wslservice`, `vmcompute`, `hns` running; `com.docker.service` Stopped (normal for WSL2 backend).
engine: **UNREACHABLE** — Windows `docker.exe` proxies through the backend; backend engine proxy has no target → all commands hang. Consistent with prior docs' finding that `dockerd`/`containerd` are missing inside the VM.

## STORAGE (read-only, verified this run via filesystem metadata)
runtime_vhdx: `C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx` — EXISTS — 0.094 GB — LastWrite 2026-08-27 23:48:40
data_vhdx: `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` — EXISTS — 103.814 GB — LastWrite 2026-08-27 23:48:40 — **INTACT, live, untouched**
factory_template: `C:\Program Files\Docker\Docker\resources\wsl\ext4.vhdx` — EXISTS — 0.094 GB — LastWrite 2026-06-26 16:52:47 — pristine runtime template
(Note: SHA256 divergence between runtime and template, and the "dockerd/containerd missing" finding, are documented in prior runs' `M1_DOCKER_RECOVERY_FINAL.md`/`M1_RECOVERY_REPORT.md`; NOT independently re-verified this run because `wsl` CLI hangs — treated as UNVERIFIED-THIS-RUN but carried as prior evidence.)

## TOPOLOGY (verified facts only)
1. Runtime (rootfs) VHDX = `main\ext4.vhdx` (per registry `BasePath` of `docker-desktop` distro).
2. Persistent Docker data (images/volumes/containers) VHDX = `disk\docker_data.vhdx` (103.8 GB).
3. `disk\docker_data.vhdx` is NOT a registered WSL distro and is NOT under any distro BasePath → it is a **separate file that Docker Desktop mounts into the VM** (newer single-distro layout; corroborated by prior docs citing Docker official docs + docker/for-win #14901/#14918).
4. Docker Desktop launches `docker-desktop` distro and attaches `docker_data.vhdx` as Docker root (`/var/lib/docker`). Rebuilding the runtime distro re-attaches the same data disk.
5. Officially documented recovery (Docker docs + docker/for-win #14918): missing/runtime ext4.vhdx → `wsl --unregister docker-desktop` then relaunch; Docker recreates the runtime from template and re-attaches the data disk. **VERIFIED by documentation + registry BasePath proof** (not by experiment this run).

## BACKUP
available: **NO**
destination: NONE — `C:` is the only fixed disk (952.6 GB total, **6.6 GB FREE**); a 1.2 GB system volume also shows 0.1 GB free. No removable/external/USB/network target detected.
verified: N/A — no backup taken. Data disk (103.8 GB) cannot be duplicated to `C:` (6.6 GB free).

## CREDENTIAL
status: UNKNOWN (active/inactive not determinable this run). Per `RESUME_AUDIT.md` + prior docs, a DB credential was exposed in an earlier diagnostic → **CREDENTIAL ROTATION REQUIRED = YES** (precaution). Not printed, not rotated this run.

## RECOVERY OPTIONS
A. Non-destructive Docker Desktop repair (Quit + relaunch / Troubleshoot→Restart)
   - SUPPORTED: yes (Docker Desktop normal operation). EVIDENCE: prior transient engine-down fixed by restart (M1_ENVIRONMENT.md). DATA RISK: NONE. REVERSIBLE: yes. BACKUP REQUIRED: no. OPERATOR ACTION: Quit + relaunch. NOTE: prior evidence says INSUFFICIENT to fix missing engine binaries, but it is the only zero-risk step and may clear the current `wsl.exe` hang/restoring CLI observability.

B. Runtime re-provision via `wsl --unregister docker-desktop` + relaunch
   - SUPPORTED: yes (Docker docs + docker/for-win #14918; registry BasePath proof: deletes ONLY `main\ext4.vhdx`). EVIDENCE: documented + community-confirmed for 4.77/4.80 single-distro layout. DATA RISK: LOW if `docker_data.vhdx` backed up first; data disk is separate file outside BasePath so unregister does NOT touch it. REVERSIBLE: restore data disk from backup if needed. BACKUP REQUIRED: YES (≥110 GB verified copy). OPERATOR ACTION: required + explicit authorization. NOT executed.

C. Backup + surgical runtime replacement (copy template binaries into VM)
   - SUPPORTED: no (blocked). EVIDENCE: agent lacks admin to `wsl --mount` template VHDX ("Access is denied" in prior run). DATA RISK: lowest (non-destructive). REVERSIBLE: yes. BACKUP REQUIRED: recommended. OPERATOR ACTION: needs admin elevation. NOT executed.

D. Reinstall + data restoration
   - SUPPORTED: yes (Docker installer). EVIDENCE: Docker docs require backing up data VHDX before reinstall. DATA RISK: MEDIUM-HIGH (installer may wipe wsl dir if no backup). REVERSIBLE: only with backup. BACKUP REQUIRED: YES. OPERATOR ACTION: high. NOT preferred.

E. WSL unregister (explicit)
   - Same mechanism/risk as B. SUPPORTED: yes. DATA RISK: LOW-with-backup. BACKUP REQUIRED: YES. NOT executed.

F. Other
   - Factory reset / "Reset to factory defaults": PROHIBITED — deletes BOTH runtime + data VHDX (total loss). DO NOT USE.

## RECOMMENDED NEXT ACTION (ONE SINGLE ACTION)
**Operator performs a NON-DESTRUCTIVE Docker Desktop restart (Quit via Task Manager/UI, then relaunch).** This carries NO data risk, requires no backup, and is the only safe step that can clear the current `wsl.exe` hang and restore CLI observability so the runtime binary state can be re-confirmed. The actual runtime recovery (rebuild of `main\ext4.vhdx` via Option B/E) remains BLOCKED until (1) a verified ≥110 GB external backup of `disk\docker_data.vhdx` exists and (2) the operator explicitly authorizes the runtime rebuild.

## BLOCKERS
1. Docker runtime corruption (engine binaries missing from `main\ext4.vhdx`) — requires backup-gated, operator-authorized runtime rebuild.
2. `wsl.exe` CLI now hangs (new this run) — blocks re-verification of binary state; a non-destructive restart is the first mitigation.
3. No ≥110 GB backup destination — makes any destructive recovery unsafe (OXYGEN rule).
4. Separate `yarn ESOCKETTIMEDOUT` build blocker (M1_BUILD_BLOCKER.md) — independent of Docker; resolve only after Docker is healthy.
5. Exposed DB credential requires rotation before any sensitive use (post-recovery, pre-go-live).

## UNKNOWN
- Whether `dockerd`/`containerd` are still missing inside the VM (could not re-verify because `wsl` CLI hangs).
- Whether the `wsl.exe` hang is a fresh wedge (e.g., stuck docker-desktop VM) or a deeper regression.
- Whether restart alone restores `wsl` CLI responsiveness.
- Active/inactive status of the exposed credential.
- Exact re-attach behavior of Docker Desktop 4.80 on relaunch after runtime deletion — verified by documentation/registry proof, but NOT by live experiment this run.

---
*Agent status: STOPPED at OXYGEN boundary. No VHDX deleted/unregistered/mounted-written. Contec source untouched. No destructive action taken.*
