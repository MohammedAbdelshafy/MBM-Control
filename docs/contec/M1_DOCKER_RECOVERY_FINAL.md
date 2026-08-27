# CONTEC M1 — SURGICAL DOCKER DESKTOP RECOVERY — FINAL REPORT

**Mode this run:** STRICTLY READ-ONLY FORENSIC + DOCUMENTATION.
**No destructive action executed.** No VHDX deleted/overwritten. No binary copied. No VHDX mounted-written. No `wsl --unregister`. Contec source untouched.

**Generated:** 2026-08-27 (this run)
**Environment:** Windows 11 (Build 26200.9168), WSL 2.7.8.0, kernel 6.18.33.1-1, Docker Desktop 4.80.0.

---

## 0. Mission & absolute prohibitions (honored)

Recover the Docker Desktop runtime so the M1 bake-off (S01–S17) can resume, **without risking Contec source or Docker data**.

Prohibited this run (all honored):
- Uninstall / factory reset / `wsl --unregister`
- Delete `docker_data.vhdx` / delete volumes / delete images / `docker system prune` / `docker volume prune`
- Delete Docker WSL data dir / delete or overwrite any VHDX / manually mount-write VHDX
- Copy binaries directly into the damaged filesystem
- Disable Windows security / modify Contec source

**Result: this run produced diagnostics + this document only. It did NOT repair Docker.** Recovery requires an operator-approved, backup-verified, *destructive-to-runtime* action (see Phase 10).

---

## 1. PHASE 1 — Physical path confirmation (read-only)

| Path | Size | LastWrite | SHA256 | Role |
|---|---|---|---|---|
| `C:\Users\omare\AppData\Local\Docker\wsl\main\ext4.vhdx` | 96 MB | 2026-08-27 22:46:56 | `123F99FE3378FD84D7422ED2D6477011A95E2246B9B1087DEC74A45617E2F26C` | **Runtime rootfs (CORRUPTED)** |
| `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` | 103.81 GB | 2026-08-27 19:12:17 | *(skipped — 104 GB, not reasonably safe to hash this run)* | **Data disk (INTACT, live)** |
| `C:\Program Files\Docker\Docker\resources\wsl\ext4.vhdx` | 96 MB | 2026-06-26 16:52:47 | `6477A23E6F9009964BBF2B031EE108B0F92D3A3B2968263C2BE53134B94569DE` | **Pristine template** |

**Critical finding:** the runtime `main\ext4.vhdx` SHA256 **differs** from the pristine template (`123F99FE…` vs `6477A23E…`). The runtime is a *divergent/corrupted* copy, not the template. This is why the engine binary is absent (see M1_RECOVERY_REPORT.md: `/usr/local/bin/dockerd` and `/usr/bin/containerd` confirmed MISSING from the VM).

---

## 2. PHASE 2 — WSL topology

```
wsl --status   → Default Distribution: docker-desktop | Default Version: 2
wsl --version  → WSL 2.7.8.0, kernel 6.18.33.1-1
wsl -l -v      → NAME: docker-desktop  STATE: Stopped  VERSION: 2
```

Only **one** registered distro (`docker-desktop`). No separate `docker-desktop-data` distro. The data lives in an attached data disk, not a second distro (confirmed by Phase 3 + Docker docs).

---

## 3. PHASE 3 — Distro ↔ VHDX mapping (registry proof, read-only)

Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss`:
```
Distro: docker-desktop | BasePath=\\?\C:\Users\omare\AppData\Local\Docker\wsl\main | State=1 | Version=2
```

**Proof:** the `docker-desktop` distro's rootfs is `…\Docker\wsl\main\ext4.vhdx`. WSL stores a distro's VHDX at `<BasePath>\ext4.vhdx`, so `wsl --unregister docker-desktop` would delete **only `main\ext4.vhdx`** — never `disk\docker_data.vhdx` (which is outside BasePath).

`disk\docker_data.vhdx` is **not** referenced by any registered distro → it is an external data disk Docker Desktop mounts into the `docker-desktop` VM (newer single-distro layout; see Phase 5). **Data ownership: intact and separate from the runtime.**

---

## 4. PHASE 4 — Safe backup destination

`C:` is the only disk, **17.9 GB free**. The data disk is **103.81 GB**.
**Backup destination: UNAVAILABLE locally.** A verified backup requires external storage ≥110 GB (VHDX + margin). Without it, any runtime rebuild is NOT safely backed.

---

## 5. PHASE 5 — Non-destructive recovery investigation (VERIFIED, not guessed)

Sources (Docker official + community-verified, matching this exact topology):
- **Docker official backup docs** (`docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/`): on Windows, back up `%LOCALAPPDATA%\Docker\wsl\data\docker_data.vhdx` to preserve containers/images → confirms the data disk is a *separate* file from the runtime.
- **Exxer "Docker Desktop / WSL2 recovery" (tested Docker Desktop 4.77, identical layout):** `main\ext4.vhdx` (~0.1 GB, engine OS/bootstrap) is **disposable — Docker rebuilds it**; `disk\docker_data.vhdx` (tens of GB) is **your data — never touch**. Fix: back up data disk, then `wsl --unregister docker-desktop`; Docker recreates the runtime and re-attaches the data disk.
- **GitHub docker/for-win #14901:** newer Docker Desktop mounts data as an external disk into the single `docker-desktop` distro (no `docker-desktop-data` distro) — matches this install (4.80.0).
- **GitHub docker/for-win #14918 (Docker Support reply):** missing runtime ext4.vhdx → `wsl --unregister docker-desktop` then restart Docker Desktop; the distro and missing ext4.vhdx are recreated automatically.

**Verified conclusion:** In Docker Desktop 4.x, the runtime (`main\ext4.vhdx`) and the data disk (`disk\docker_data.vhdx`) are **independent files**. Rebuilding the runtime (`wsl --unregister docker-desktop` + relaunch) **preserves** the data disk. This is documented + community-confirmed, and consistent with our registry proof (BasePath = main).

**However:** this rebuild is *destructive to the runtime VHDX* (deletes `main\ext4.vhdx`) and requires a **verified backup of `disk\docker_data.vhdx`** before execution. Per this run's prohibitions + Phase 4 (no backup possible), it was **NOT executed**.

No fully non-destructive repair exists that restores the missing `dockerd`/`containerd` binaries: copying binaries into the damaged FS is prohibited and blocked (no admin to mount the template VHDX; `wsl --mount` returned "Access is denied"). `wsl --update` only refreshes the WSL kernel, not the engine binaries inside the corrupted runtime VHDX.

---

## 6. PHASE 6 — Safest order (for operator, NOT executed this run)

1. Attach external storage ≥110 GB.
2. Quit Docker Desktop fully (`taskkill /F /IM "Docker Desktop.exe"`), `net stop com.docker.service`, `wsl --shutdown`.
3. **Back up** `C:\Users\omare\AppData\Local\Docker\wsl\disk\docker_data.vhdx` to external storage. Hash-verify.
4. `wsl --unregister docker-desktop` (removes only `main\ext4.vhdx`).
5. Relaunch Docker Desktop → recreates runtime from template, re-attaches data disk.
6. Verify: `docker version`, `docker info`, `docker images` show prior images/volumes.

---

## 7. PHASE 7 — Binary copying

**Not performed.** Prohibited by mission; also impossible (agent lacks admin to `wsl --mount` the template; `wsl --mount` returned "Access is denied").

---

## 8. PHASE 8 — Post-repair health test

**N/A this run.** No action taken → no health test possible. (After operator recovery: `docker version` + `docker info` + `docker ps -a` must succeed.)

---

## 9. PHASE 9 — Contec data verification

**N/A this run.** Docker engine is down; `contec` app data lives inside the (intact) data disk and was **not touched**. After recovery, verify `deployment/contec/frappe_docker` + `apps/contec` are intact on host and that the frappe/erpnext + mariadb containers/images remain in the data disk.

---

## 10. VERDICT & REQUIRED OPERATOR ACTION — STOP

**Root cause (confirmed):** Docker Desktop VM runtime root-fs corruption — engine binaries (`dockerd`, `containerd`) missing from `main\ext4.vhdx`; runtime VHDX diverges from the pristine template. CLI hangs because the backend engine proxy has no target.

**DESTRUCTIVE ACTION REQUIRED for recovery: YES** (rebuild runtime via `wsl --unregister docker-desktop`), but **NOT authorized/executed this run**.

**DATA LOSS RISK if done wrong:** LOW if `disk\docker_data.vhdx` is backed up first; the rebuild removes only the runtime VHDX (registry-proven). Risk arises only if the data disk is also removed or not backed up.

**OPERATOR ACTION REQUIRED (separate, explicit authorization):**
1. Attach ≥110 GB external storage.
2. Approve + run the Phase 6 backup (verify hash).
3. Approve + run `wsl --unregister docker-desktop` + relaunch Docker Desktop.
4. Do **NOT** factory-reset / unregister without the backup.

**This run stops here. No further automated action.**

---

## 11. SECRET SAFETY

A database credential was exposed in an earlier diagnostic log. Treat as **COMPROMISED**. Rotate before any sensitive use. Do **not** print, commit, or reuse the exposed value. (No secret is recorded in this document.)

---

## 12. OUTSTANDING BLOCKERS (unchanged)

- **Blocker A (this run):** Docker runtime corruption — requires operator-approved, backup-verified runtime rebuild (Phase 10).
- **Blocker B:** Separate `yarn` `ESOCKETTIMEDOUT` (`registry.yarnpkg.com/…/ace-builds-1.31.2.tgz`) preventing S01 custom `contec` image build. Tracked in `docs/contec/M1_BUILD_BLOCKER.md` (Option B: offline mirror / registry proxy). Must be resolved after Docker is healthy.

---

## 13. REFERENCES

- `docs/contec/M1_RECOVERY_REPORT.md` — definitive VM-corruption root cause + forensic pipeline.
- `docs/contec/M1_DOCKER_RECOVERY_STATUS.md` — prior status + recovery options.
- `docs/contec/M1_BUILD_BLOCKER.md` — yarn network blocker.
- `docs/contec/M1_ENVIRONMENT.md`, `RESUME_AUDIT.md`, `M1_INSTALL_LOG.md`, `PLATFORM_BAKEOFF.md`.
- Docker official: `docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/`
- Exxer recovery article (Docker Desktop 4.77, matching topology).
- GitHub docker/for-win #14901, #14918.
