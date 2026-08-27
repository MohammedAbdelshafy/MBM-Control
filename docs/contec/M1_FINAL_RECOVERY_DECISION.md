# CONTEC M1 — FINAL RECOVERY DECISION

**Mode:** READ-ONLY FORENSIC + DECISION. NO STORAGE MODIFICATION this run.
**Date:** 2026-08-28 (restart after OpenCode crash). **Agent:** HY3
**OXYGEN RULE:** triggered — no ≥110 GB backup destination → destructive recovery NOT authorized.

---

## ROOT CAUSE
Docker Desktop `docker-desktop` runtime root-fs corruption: engine binaries `dockerd` and `containerd` missing from `main\ext4.vhdx` (per prior forensic runs `M1_RECOVERY_REPORT.md` / `M1_DOCKER_RECOVERY_FINAL.md`, carried as evidence — NOT independently re-verified this run because `wsl.exe` CLI hangs). Windows `docker.exe` proxies every command through the backend engine proxy, which has no target → all Docker CLI commands hang. NEW this run: `wsl.exe` CLI itself hangs (prior docs reported it healthy), so live re-verification of the in-VM binary state is blocked.

## CONFIDENCE
MEDIUM for "engine binaries missing inside VM" (carried from prior high-confidence docs, not re-confirmable now due to hung `wsl` frontend). HIGH that the persistent data VHDX is intact and is a file separate from the runtime distro (registry BasePath proof + filesystem metadata, both verified this run).

---

## RUNTIME VHDX
`C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx`
EXISTS — 0.094 GB — LastWrite 2026-08-27 23:48:40
Role: `docker-desktop` distro rootfs (runtime/engine OS). Corrupted layer.

## DATA VHDX
`C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx`
EXISTS — 103.814 GB — LastWrite 2026-08-28 00:06:07
Role: persistent Docker data (images / volumes / containers / databases). INTACT, live, untouched.

## FACTORY TEMPLATE
`C:\Program Files\Docker\Docker\resources\wsl\ext4.vhdx`
EXISTS — 0.094 GB — LastWrite 2026-06-26 16:52:47
Role: pristine runtime the engine would be rebuilt from.

---

## AVAILABLE DISKS (read-only enumeration)
- `:` Fixed 1.2 GB total / 0.1 GB free (system reserved)
- `C:` Fixed 952.6 GB total / **20.1 GB free** (only fixed volume)
- Removable / external / USB: NONE detected
- Network mapped storage: NONE detected

## BACKUP DESTINATION
NO ≥110 GB destination exists. `C:` (20.1 GB free) cannot hold a copy of the 103.8 GB data VHDX. No external/removable/network target.

## BACKUP STATUS
DATA BACKUP AVAILABLE: NO
BACKUP VERIFIED: NO (no backup taken)

---

## RECOVERY OPTIONS

### A. Docker Desktop restart (Quit + relaunch / Troubleshoot → Restart)
- SUPPORTED: yes (normal Docker Desktop operation)
- EVIDENCE: prior transient engine-down resolved by normal restart (`M1_ENVIRONMENT.md`); Docker Desktop handles this with no persistent change
- DATA IMPACT: none — preserves everything; deletes nothing
- BACKUP REQUIRED: no
- REVERSIBILITY: trivial (fully reversible)

### B. Supported runtime recovery — `wsl --unregister docker-desktop` + relaunch
- SUPPORTED: yes (per Docker Support, docker/for-win #14918: missing runtime ext4.vhdx → unregister then restart; Docker recreates the distro)
- EVIDENCE: (1) Registry BasePath of `docker-desktop` = `...\Docker\wsl\main` → unregister removes ONLY `<BasePath>\ext4.vhdx` (runtime), NOT `disk\docker_data.vhdx` (outside BasePath). (2) Docker official backup docs identify `%LOCALAPPDATA%\Docker\wsl\data\docker_data.vhdx` as a SEPARATE file to back up → data disk is independent of the runtime distro. (3) docker/for-win #14901 documents the newer single-distro layout where data is an external disk mounted into `docker-desktop`. (4) Community-verified article (Exxer, Docker Desktop 4.77, identical topology) confirms the runtime is disposable/rebuilt and the data disk is re-attached.
- DATA IMPACT: deletes ONLY the runtime VHDX (96 MB). The 103.8 GB data disk is a separate file and, per the above Docker-desktop storage behavior evidence, is re-attached on relaunch. **This is evidenced behavior, not an assumption from file separation alone.**
- BACKUP REQUIRED: YES (verified ≥110 GB copy of `docker_data.vhdx` before execution)
- REVERSIBILITY: restore data disk from backup if re-attach fails

### C. Runtime VHDX replacement/reprovisioning (copy template binaries into VM in place)
- SUPPORTED: no (blocked this run)
- EVIDENCE: agent lacks admin to `wsl --mount` the template VHDX (prior run returned "Access is denied"); mission prohibits mounting-written VHDX
- DATA IMPACT: none if it were possible (most non-destructive option)
- BACKUP REQUIRED: recommended
- REVERSIBILITY: yes

### D. WSL unregister (explicit)
- SUPPORTED: yes (same mechanism/evidence as B)
- EVIDENCE: same as B (registry BasePath proof + Docker docs)
- DATA IMPACT: same as B (runtime only; data disk separate file, re-attached)
- BACKUP REQUIRED: YES
- REVERSIBILITY: restore from backup

### E. Uninstall / reinstall Docker Desktop
- SUPPORTED: yes (Docker installer)
- EVIDENCE: Docker docs require backing up the data VHDX before reinstall
- DATA IMPACT: MEDIUM-HIGH — installer may wipe the `wsl` data dir if no backup exists; data loss possible
- BACKUP REQUIRED: YES (mandatory)
- REVERSIBILITY: only with backup

### F. Factory reset / "Reset to factory defaults"
- SUPPORTED: yes (Docker Desktop UI action)
- EVIDENCE: Docker Desktop behavior wipes runtime + data VHDX
- DATA IMPACT: CATASTROPHIC — total loss of images/volumes/containers/databases
- BACKUP REQUIRED: YES (but even then, destroys current state)
- REVERSIBILITY: none
- VERDICT: PROHIBITED by mission + OXYGEN rule. DO NOT USE.

---

## RECOMMENDED OPTION
**B. Backup required before runtime recovery.**

WHY: The runtime layer (`main\ext4.vhdx`) is the confirmed failing component, and the only working fix is a runtime rebuild (Option B/D) that deletes the 96 MB runtime VHDX and lets Docker Desktop re-create it from the factory template while re-attaching the separate 103.8 GB data disk. That re-attach is **evidenced** by Docker's own documentation + registry BasePath proof + docker/for-win #14918 + community verification — NOT merely assumed from physical file separation. However, the mission rule is explicit: *if no ≥110 GB backup destination exists, do NOT recommend destructive recovery as the immediate action.* No such destination exists on this machine (`C:` = 20.1 GB free; no external/removable/network storage). Therefore the safe verified path is: (1) perform the non-destructive restart (Option A) now to restore `wsl`/CLI observability and confirm the binary state, then (2) **defer the destructive runtime rebuild until a verified ≥110 GB backup of `docker_data.vhdx` exists and the operator explicitly authorizes it.** A non-destructive restart is safe to do immediately; the destructive rebuild is NOT safe to do yet.

---

## DATA LOSS RISK
LOW if `docker_data.vhdx` is backed up before the runtime rebuild (data disk is a separate file, re-attached per documented Docker behavior). MEDIUM-UNKNOWN if the rebuild is attempted WITHOUT a backup (relies on documented re-attach not yet confirmed by live experiment on this exact install). Current status: data disk is **PRESERVED** (intact, untouched).

## CREDENTIAL STATUS
ROTATION REQUIRED: YES (a DB credential was exposed in an earlier diagnostic; per `RESUME_AUDIT.md` treat as compromised)
ROTATION COMPLETE: NO
UNKNOWN: active/inactive state not determinable this run

## OPERATOR ACTION REQUIRED
YES. Agent will not delete/unregister/rebuild anything. Operator must:
1. (Now, safe) Quit + relaunch Docker Desktop to clear the `wsl.exe` hang and restore observability; re-confirm `dockerd`/`containerd` absence.
2. Attach external/network storage ≥110 GB (or free ≥110 GB elsewhere).
3. Back up `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` (hash-verify source vs copy).
4. Approve + run `wsl --unregister docker-desktop`, then relaunch Docker Desktop (runtime rebuilt from template, data disk re-attached).
5. Do NOT factory-reset / reinstall / prune.
6. After Docker healthy, rotate the exposed DB credential before any sensitive use; then resolve the separate `yarn ESOCKETTIMEDOUT` build blocker (`M1_BUILD_BLOCKER.md`) and resume M1.

## NEXT SINGLE ACTION
Operator performs a NON-DESTRUCTIVE Docker Desktop restart (Quit via Task Manager/UI, then relaunch) to clear the `wsl.exe` hang and restore CLI observability. Do NOT proceed to the runtime rebuild until a verified ≥110 GB external backup of `disk\docker_data.vhdx` exists and the operator explicitly authorizes the rebuild.

---
*Agent status: STOPPED at OXYGEN boundary. No VHDX deleted/unregistered/mounted-written. Contec source untouched. No destructive action taken.* 2026-08-28 HY3.
