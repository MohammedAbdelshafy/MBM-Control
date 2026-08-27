# CONTEC M1 — SMART DOCKER RECOVERY

**Mode this run:** READ-ONLY FORENSIC + DECISION. No destructive action executed.
**Date:** 2026-08-27 · **Agent:** HY3
**OXYGEN RULE:** triggered (no backup destination + runtime rebuild requires `wsl --unregister`) → STOP, DOCUMENT, ESCALATE.

> **Correction to prior doc:** `docs/contec/M1_DOCKER_RECOVERY_STATUS.md` (written before this
> session's registry proof) incorrectly states `wsl --unregister docker-desktop` would delete BOTH
> VHDXes. This is **wrong** for the current install. Registry proof + Docker official docs show the
> data disk `disk\docker_data.vhdx` is a SEPARATE file OUTSIDE the distro BasePath (`main`), so
> unregister removes only the runtime VHDX. See DOCKER TOPOLOGY + OPTION B/E below.

---

## ROOT CAUSE
Docker Desktop `docker-desktop` VM runtime root-fs corruption: the `dockerd` and `containerd`
engine binaries are **MISSING** from `main\ext4.vhdx`. Engine cannot start; backend engine proxy has
no target; Windows `docker.exe` (proxies via backend) hangs on ALL commands incl. `docker --version`.
The data disk is a separate, intact VHDX and is NOT corrupted.

## CONFIDENCE
**HIGH.** Binaries confirmed absent (`/usr/local/bin/dockerd`, `/usr/bin/containerd` missing; only
`docker → wsl-bootstrap` shim remains). Runtime VHDX SHA256 (`123F99FE…`) differs from pristine
template (`6477A23E…`). Data VHDX (103.81 GB) present, LastWrite 2026-08-27 19:12 (live). WSL healthy.
Docker official docs + matching-version community article + GitHub docker/for-win #14901/#14918 confirm
the data-disk-is-separate topology.

## RUNTIME VHDX
`C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx` — 96 MB — LastWrite 2026-08-27 22:46:56
SHA256 `123F99FE3378FD84D7422ED2D6477011A95E2246B9B1087DEC74A45617E2F26C` — **CORRUPTED** (diverged
from template; engine binaries absent).

## DATA VHDX (primary protected asset)
`C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` — 103.81 GB — LastWrite 2026-08-27 19:12:17
— **INTACT, live, untouched.** Holds images / containers / volumes / databases. NEVER deleted/moved/
overwritten this run.

## FACTORY TEMPLATE
`C:\Program Files\Docker\Docker\resources\wsl\ext4.vhdx` — 96 MB — LastWrite 2026-06-26 16:52:47
SHA256 `6477A23E6F9009964BBF2B031EE108B0F92D3A3B2968263C2BE53134B94569DE` — pristine runtime the
engine would be rebuilt from.

## WSL TOPOLOGY
- WSL 2.7.8.0, kernel 6.18.33.1-1, Default Version 2, Default Distro `docker-desktop`.
- `wsl -l -v` → **only ONE** distro: `docker-desktop` (Stopped, v2). No `docker-desktop-data` distro.
- Registry `HKCU\...\Lxss`: `docker-desktop` BasePath = `\\?\C:\Users\omare\AppData\Local\Docker\wsl\main`.
  ⇒ distro rootfs = `main\ext4.vhdx`. `wsl --unregister docker-desktop` deletes ONLY `<BasePath>\ext4.vhdx`
  = runtime; it does NOT touch `disk\docker_data.vhdx` (outside BasePath).

## DOCKER TOPOLOGY
- Newer single-distro model (Docker Desktop 4.x): `docker-desktop` distro rootfs = `main\ext4.vhdx`
  (engine OS/bootstrap, ~0.1 GB, **disposable**); data disk `disk\docker_data.vhdx` (~104 GB) is an
  **external disk Docker Desktop mounts into the VM** (per for-win #14901). They are independent files.
- Link: Docker Desktop launches the `docker-desktop` distro and attaches `docker_data.vhdx` as the
  Docker root (`/var/lib/docker`). Rebuilding the runtime distro re-attaches the same data disk.
- `M1_RECOVERY_REPORT.md`'s older path `C:\ProgramData\DockerDesktop\vm-data` is from a previous layout;
  the **proven current** data location is `disk\docker_data.vhdx`.
- Contec source lives on the WINDOWS filesystem (`apps/contec`, `deployment/contec/frappe_docker`,
  `docs/contec/*`) → unaffected by Docker VM corruption.

## BACKUP
**AVAILABLE / VERIFIED:** NO.
- Only physical disk = Samsung 953 GB, single volume `C:` with **17.52 GB free** (re-verified this run).
- No external disk, no `D:`/`E:`, no network/USB target detected.
- Data disk is 103.81 GB → cannot be duplicated to `C:`.
- **No backup taken. Backup is REQUIRED before any destructive recovery.**

## RECOVERY OPTIONS

### OPTION A — Docker Desktop supported restart/repair (Quit + relaunch; Troubleshoot → Restart)
- CHANGES: nothing persistent. PRESERVES: everything. CAN DELETE: nothing.
- RECOVERY/ROLLBACK: trivial. EVIDENCE: earlier transient engine-down was fixed by normal restart
  (M1_ENVIRONMENT.md). RISK: **NONE** — but **INSUFFICIENT**: binaries are physically missing from the
  VHDX; a restart cannot recreate them.

### OPTION B — Runtime re-provision via `wsl --unregister docker-desktop` + relaunch
- CHANGES: deletes `main\ext4.vhdx` (runtime), Docker Desktop recreates it from the template and
  re-attaches `disk\docker_data.vhdx`. PRESERVES: data disk (separate file, outside BasePath).
- CAN DELETE: ONLY the runtime VHDX. RECOVERY/ROLLBACK: restore data disk from backup if needed.
- EVIDENCE: Docker official backup docs (data disk is separate file); Exxer article (4.77, identical
  topology: unregister preserves data disk); GitHub docker/for-win #14918 (Docker Support recommends
  exactly this); registry BasePath proof. RISK: **LOW data-loss IF data disk backed up**; MEDIUM if not
  backed up (relies on unverified-by-experiment re-attach). **Requires backup + operator authorization.**

### OPTION C — Docker Desktop reinstall while preserving backed-up data
- CHANGES: program files + possibly WSL data dir. PRESERVES: only if `docker_data.vhdx` backed up and
  restored. CAN DELETE: data if installer wipes the wsl dir and no backup exists.
- EVIDENCE: Docker docs say back up data VHDX before reinstall. RISK: MEDIUM-HIGH. Not preferred.

### OPTION D — Factory reset / "Reset to factory defaults" / Clean-Purge
- CHANGES: wipes everything. PRESERVES: nothing. CAN DELETE: runtime + data VHDX (total loss of
  images/volumes/containers/databases). EVIDENCE: Docker Desktop behavior. RISK: **CATASTROPHIC** —
  explicitly PROHIBITED by mission + OXYGEN RULE. DO NOT USE.

### OPTION E — WSL unregister (explicit)
- Same mechanism as OPTION B. CHANGES/PRESERVES/CAN DELETE as B. EVIDENCE as B. RISK as B.
- Requires backup + operator authorization. NOT executed this run.

### (Non-destructive ideal, BLOCKED) — In-place binary copy from template
- Mount pristine template read-only, copy `dockerd`/`containerd` into VM. Fully non-destructive.
- BLOCKED: agent lacks admin to `wsl --mount` the template VHDX (returned "Access is denied"). Would be
  the safest fix if admin were available.

## RECOMMENDED OPTION
**OPTION B/E** (runtime rebuild via `wsl --unregister docker-desktop` + relaunch) — the only
data-preserving working fix, per Docker's own support guidance and our registry proof.
**WHY:** it removes ONLY the corrupted runtime VHDX (96 MB, disposable) and re-attaches the intact,
separate 104 GB data disk. All safer options (A) are insufficient; all riskier options (C/D) threaten data.
**BUT it is NOT executable this run** because (1) no backup destination exists (OXYGEN RULE: backup
required before destructive action) and (2) the mission requires explicit operator authorization.

## OPERATOR AUTHORIZATION REQUIRED
**YES.** Agent will not delete/unregister/rebuild anything. Operator must:
1. Attach external storage ≥110 GB (or free ≥110 GB elsewhere).
2. Back up `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` (hash-verify source vs copy).
3. Approve + run `wsl --unregister docker-desktop`, then relaunch Docker Desktop.
4. Do NOT factory-reset / reinstall / prune.

## DOCKER STATUS
**BLOCKED** (engine binaries missing; CLI hangs).

## DATA STATUS
**PRESERVED** (data VHDX intact, untouched, separate from corrupted runtime). At risk only if a
non-data-preserving recovery is attempted without backup.

## CONTEC STATUS
**PRESERVED** (source on Windows FS: `apps/contec`, `deployment/contec/frappe_docker`, `docs/contec/*`
untouched this run and by the corruption).

## M1 STATUS
**BLOCKED** (Docker down + separate yarn `ESOCKETTIMEDOUT` build blocker — M1_BUILD_BLOCKER.md).

---

## SECRET INCIDENT (Step 7)
- A DB credential was exposed in an earlier recovered in-memory `.env` (not in git history / tracked files).
- TREAT AS COMPROMISED. NEVER PRINT THE SECRET.
- **CREDENTIAL_ROTATION: REQUIRED** (precaution, per RESUME_AUDIT.md).
- Not performed this run (storage/recovery state uncertain; do not risk rotation now). Rotate only after
  Docker is healthy and before any sensitive use.

## FILES CHANGED
- CREATED: `docs/contec/M1_DOCKER_SMART_RECOVERY.md` (this file).
- No application code, no Contec source, no Docker data modified. This run is documentation-only.

## COMMITS
- None. (Git rule: recovery docs only; no reset/clean/force-push/branch deletion.)

## NEXT SINGLE SAFE ACTION (operator)
Attach ≥110 GB external storage → back up `disk\docker_data.vhdx` (hash-verify) → authorize
`wsl --unregister docker-desktop` + relaunch Docker Desktop → verify (`docker version`/`info`/`ps` and
that images/volumes/containers persist). Then resolve the yarn `ESOCKETTIMEDOUT` blocker (M1_BUILD_BLOCKER.md
Option B offline mirror) and resume M1 S01. Rotate the exposed DB credential before sensitive use.

**Agent status: STOPPED at OXYGEN boundary. No destructive action taken. Contec source untouched.**
