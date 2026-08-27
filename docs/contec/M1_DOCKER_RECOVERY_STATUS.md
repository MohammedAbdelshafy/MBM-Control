# CONTEC M1 — DOCKER DESKTOP RECOVERY STATUS

Generated: 2026-08-27 (HY3, forensic data-preserving mode)
Prerequisite report: docs/contec/M1_RECOVERY_REPORT.md

---

## ROOT CAUSE
Docker Desktop `docker-desktop` **runtime VHDX** (`main\ext4.vhdx`, 96 MB) is corrupted:
the Linux `dockerd` and `containerd` engine binaries are **missing** from the VM root
filesystem. The engine therefore cannot start; the backend's engine proxy has no target
(backend internal `GET /ping` → `context deadline exceeded`); and the Windows `docker.exe`
(which proxies every command through the backend) hangs on ALL commands, including the
daemon-free `docker --version`.

The **Docker DATA disk** (`disk\docker_data.vhdx`, ~104 GB) is a SEPARATE, intact VHDX
holding images/volumes/containers — it is NOT corrupted.

## CONFIDENCE
HIGH. `/usr/local/bin/dockerd` and `/usr/bin/containerd` directly confirmed absent via
`wsl -d docker-desktop -- ls`. Pristine runtime template `resources\wsl\ext4.vhdx` (same
96 MB size) ships with Docker Desktop. Data VHDX is separate and large (104 GB).

## DOCKER APP
Docker Desktop 4.80.0 installed (from backend log). Application/backend not itself corrupted;
fully stopped now (only `wslservice` running; `docker-desktop` distro Stopped).

## DOCKER ENGINE
dockerd + containerd **binaries missing inside VM** → engine non-functional. Backend alive
but engine proxy has no target. 24 containerd-shims were alive only via held deleted inodes;
after the earlier diagnostic kill, the engine cannot restart (binary gone).

## WSL
WSL2 2.7.8.0 healthy. `docker-desktop` distro reachable but Stopped (corrupted rootfs).
NOTE: in this install there is only ONE registered distro (`docker-desktop`) that uses TWO
VHDXes — `main\ext4.vhdx` (runtime) and `disk\docker_data.vhdx` (data). There is NO separate
`docker-desktop-data` distro, so `wsl --unregister docker-desktop` would delete BOTH → data loss.

## DOCKER DATA LOCATION
- Runtime (corrupted): `C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx` (96 MB)
- Data (intact):        `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` (~104 GB)
- Pristine template:     `C:\Program Files\Docker\Docker\resources\wsl\ext4.vhdx` (96 MB)

## CONTEC DATA LOCATION
Contec source is on the WINDOWS filesystem, NOT inside Docker → unaffected by this corruption:
- `apps/contec` (contec app skeleton)
- `deployment/contec/frappe_docker` (official, pinned v3.2.2)
- `docs/contec/*` (all recovery docs)
No Contec database/app volumes lived in Docker in a way that this blocks at the source level.

---

## BACKUP
STATUS: NOT PERFORMED — impossible on this machine.
SOURCE: `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` (104 GB)
DESTINATION: NONE AVAILABLE — only `C:` exists with 17.9 GB free; no secondary/external disk.
VERIFIED: N/A (no backup taken).
→ Operator must attach ≥110 GB external storage (or free space) before any destructive repair.

---

## RECOVERY OPTIONS
1. (RECOMMENDED, LOW data risk) **Targeted runtime rebuild**: shut down Docker Desktop,
   delete ONLY the corrupted runtime VHDX `main\ext4.vhdx`, relaunch Docker Desktop.
   Docker Desktop recreates the runtime from the pristine template `resources\wsl\ext4.vhdx`
   and re-attaches the SEPARATE data VHDX `disk\docker_data.vhdx`. Images/volumes/containers
   preserved. Requires operator authorization (deletes one VHDX).
2. (Safest but BLOCKED here) **In-place binary copy**: mount pristine template read-only,
   copy Linux dockerd/containerd into the VM. Fully non-destructive. BLOCKED — needs admin to
   `wsl --mount` the template VHDX; agent got "Access is denied". Would be the ideal fix if
   admin were available.
3. (PROHIBITED / data-loss) **"Reset to factory defaults" or reinstall**: deletes BOTH runtime
   and data VHDX → total loss of images/volumes/containers. Do NOT use.

---

## RECOMMENDED
Option 1 (targeted runtime-VHDX replacement — NOT factory reset).
WHY: rebuilds only the corrupted runtime rootfs from the shipped template while the 104 GB
data disk is a separate file that Docker Desktop re-attaches on relaunch. This is the same
mechanism as `wsl --unregister docker-desktop` + relaunch but WITHOUT unregistering, so the
data disk is untouched. Lowest data-loss risk among working fixes.

## DATA LOSS RISK
LOW for Option 1 (data VHDX is separate and not touched).
CAVEAT: no backup currently exists (insufficient free space), so risk climbs to MEDIUM if the
assumption that Docker Desktop re-attaches `disk\docker_data.vhdx` is wrong. Back up the data
VHDX (attach ≥110 GB media) BEFORE Option 1.

## OPERATOR ACTION REQUIRED
YES. The only working repair deletes a VHDX (prohibited for the agent). The non-destructive
alternative (Option 2) is blocked by lack of admin. Agent will not execute destructive recovery
without explicit operator authorization.

## DO NOT EXECUTE (agent)
- Docker Desktop "Reset to factory defaults" / factory reset
- `wsl --unregister docker-desktop` (would delete the data VHDX in this single-distro layout)
- delete/replace `disk\docker_data.vhdx` (the data disk)
- delete/replace ANY VHDX except the targeted runtime `main\ext4.vhdx` after explicit authorization
- reinstall Docker Desktop
- `docker system prune` / delete volumes / delete images
- delete Docker Desktop data
- modify/touch Contec application source code

---

## NEXT SAFE ACTION
1. Operator attaches external storage (≥110 GB) or frees ≥110 GB on C:.
2. Operator backs up `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx`
   (hash-verify source vs copy).
3. Operator performs Option 1: quit Docker Desktop; delete ONLY
   `C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx`; relaunch Docker Desktop
   (runtime rebuilt from template; data disk re-attached).
4. Verify health: `docker --version`, `docker context ls`, `docker version`, `docker info`,
   `docker ps` all return; confirm the 24 containers/images/volumes persist.
5. Only after Docker is healthy, resume Contec M1 from S01 (also resolve the separate
   `yarn ESOCKETTIMEDOUT` network blocker — M1_BUILD_BLOCKER.md, Option B offline mirror).

Agent status: STOPPED at escalation boundary. No destructive action taken. Contec source untouched.
