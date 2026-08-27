# CONTEC M1 — DOCKER IPC FORENSIC RECOVERY REPORT (2026-08-27, HY3)

Status: **BLOCKED — Docker Desktop VM corrupted (engine binaries missing).**
M1: **PENDING** (0 / 17 bake-off scenarios executed).
Evidence: definitive root cause identified. Repair requires DATA-RISK operator action → ESCALATED.

---

## DEFINITIVE ROOT CAUSE
**Docker Desktop VM (`docker-desktop` WSL distro) root-filesystem corruption: the `dockerd`
and `containerd` engine binaries are MISSING from the VM.** The engine cannot start, so the
Docker Desktop backend's engine proxy has nothing to forward to, and the Windows `docker.exe`
(which proxies every command through the backend) hangs on ALL commands — including the
daemon-free `docker --version`.

This is NOT a config issue, NOT a socket-only issue, NOT a simple daemon-down, and NOT a WSL
failure. The engine binaries themselves are gone from the VM image.

Confirmed at end of forensics:
- `/usr/local/bin/dockerd` → No such file or directory
- `/usr/bin/containerd`  → No such file or directory
- `/usr/local/bin/docker` → symlink to `/usr/local/bin/wsl-bootstrap` (only the shim remains)

The 24 `containerd-shim` processes were still alive only because they held the deleted inodes;
once the engine was killed it could not be restarted (binary absent).

---

## FORENSIC PIPELINE (Phases 1–11, all read-only until the final reversible attempts)

- **Phase 1 (CLI binary):** `docker` resolves to legit
  `C:\Program Files\Docker\Docker\resources\bin\docker.exe` v29.6.1 (Docker Inc). No rogue PATH.
  `docker --version` / `-v` / `context ls` ALL timeout (binary wedged at startup, not daemon-only).
- **Phase 2 (config):** `~/.docker/config.json` = `currentContext: desktop-linux`,
  `credsStore: desktop`, `features.hooks=true` (ai/scout/debug/compose). USERPROFILE `cli-plugins`
  dir empty.
- **Phase 3 (Windows IPC):** All Docker named pipes EXIST (`dockerDesktopLinuxEngine`,
  `docker_cli`, `dockerBackendApiServer`, …) — earlier `.NET` "dead" result was a false negative
  (pipe mode/security). `com.docker.service` = Stopped; `hns`/`vmcompute` Running.
- **Phase 4 (backend):** Backend processes alive (com.docker.backend, Docker Desktop, docker-agent).
  Backend log: at 15:45 UTC (=18:45 local, my config test) context flipped
  `desktop-linux→default→desktop-linux`; backend recreated all engine pipes and logged
  *"serving the Linux engine on \\.\pipe\dockerDesktopLinuxEngine"*. Recurring error:
  `stats GET /ping → Get "http://ipc/ping": context deadline exceeded` (backend internal IPC wedged).
- **Phase 5 (WSL↔engine):** Inside VM: `dockerd` (PID 157) + `containerd` (PID 146) running,
  **24 containerd-shims (containers alive)**, BUT `/var/run/docker.sock` MISSING and
  `/proc/net/unix` shows ZERO `docker` sockets. dockerd cmdline references a
  **missing** `/run/config/docker/daemon.json` (which defines the API `hosts` socket).
- **Phase 7b (surgical respawn):** Killed dockerd (157) → backend respawned a NEW dockerd (64054)
  stuck in `dockerd --config-file /run/config/docker/daemon.json --validate` against the absent file.
- **Phase 8 (backend log):** `engine linux/wsl run error: service command exited with code -1`,
  `attempting recovery`, then `engine stopped`, apiproxy `returning engine error`.
- **Phase 9 (reversible config repair):** Supplied a valid `/run/config/docker/daemon.json`
  (`hosts: ["unix:///var/run/docker.sock"]` + benign settings) in VM tmpfs. Backend still would not
  start dockerd (and tmpfs file would not survive a VM restart anyway).
- **Phase 10 (manual engine start):** `setsid /usr/local/bin/dockerd …` →
  `failed to execute /usr/local/bin/dockerd: No such file or directory`.
- **Phase 11 (confirm corruption):** `/usr/local/bin/dockerd` AND `/usr/bin/containerd`
  confirmed MISSING from the VM. VM root filesystem corrupted.

---

## FIRST FAILING LINK
Windows `docker.exe` → Docker Desktop backend (alive, but engine proxy has no target)
→ **in-VM engine binaries MISSING** → no dockerd/containerd → no API socket → hang.
The break is the **absent engine binaries in the Docker Desktop VM**, not the Windows side.

---

## REPAIR ATTEMPTED (all reversible / non-destructive, no data deleted)
1. (prior turn) `taskkill` Docker processes + `wsl --shutdown` + relaunch → no fix.
2. (this turn) Moved `~/.docker/config.json` aside and retried `docker --version` → still TIMEOUT
   ⇒ **config ruled out as cause**; config restored.
3. (this turn) Surgical `kill` of dockerd → revealed missing `daemon.json` and then missing binary.
4. (this turn) Wrote valid `daemon.json` into VM tmpfs → insufficient (binary gone).
5. (this turn) Manual `dockerd` start → failed (binary missing).

No images, volumes, containers, or repositories deleted. No Contec/app code or ERPNext core touched.
Credential rotation still RECOMMENDED (RESUME_AUDIT) — not performed.

---

## DATA LOCATION / RISK
- **At risk ONLY if operator resets/rebuilds:** Docker Desktop VM data (images, volumes, the 24
  running containers) at:
  - `C:\ProgramData\DockerDesktop\vm-data` (VHDX)
  - `C:\Users\omare\AppData\Local\Docker\wsl` (per backend log `wslDataFolder`)
- **SAFE (not in Docker):** Contec source — `apps/contec`, `deployment/contec/frappe_docker`,
  all `docs/contec/*` — live on the Windows filesystem, unaffected by Docker VM corruption.

---

## OXYGEN RULE TRIGGERED
Docker VHDX / data-loss risk → **STOP · DOCUMENT · ESCALATE.** I will NOT autonomously perform
factory reset / `wsl --unregister docker-desktop` / VHDX delete / Docker reinstall.

---

## NEXT SAFE ACTION (operator-authorised, data-risk)
1. **Back up Docker VM data FIRST** (operator):
   - Copy `C:\ProgramData\DockerDesktop\vm-data` and
     `C:\Users\omare\AppData\Local\Docker\wsl` to a safe location.
2. Rebuild the corrupted VM (operator decision, one of):
   - Docker Desktop → Troubleshoot → **"Reset to factory defaults"**, OR
   - `wsl --unregister docker-desktop` then relaunch Docker Desktop (rebuilds VM), OR
   - Reinstall Docker Desktop.
3. Verify health: `docker --version`, `docker context ls`, `docker version`, `docker info`,
   `docker ps` must all return; confirm the 24 containers/images are restored from backup if needed.
4. ONLY after Docker is healthy, resume Contec M1 from S01. Resolve the SEPARATE pre-existing
   `yarn ESOCKETTIMEDOUT` network blocker via the offline-mirror (Option B, M1_BUILD_BLOCKER.md).

## M1 STATUS
PENDING — 0/17. No M1 bake-off scenario executed. Two independent blockers remain:
(1) Docker Desktop VM corruption [THIS report]; (2) yarn `ESOCKETTIMEDOUT` in S01 build
[M1_BUILD_BLOCKER.md]. M1 is NOT complete; do not claim completion without S01–S17 evidence.
