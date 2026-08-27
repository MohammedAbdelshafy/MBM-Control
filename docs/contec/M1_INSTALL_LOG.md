# M1 INSTALL LOG — Reproducible Environment (S01 evidence)

Status: IN PROGRESS · Executor: OX ALPHA · Charter: PLATFORM_BAKEOFF.md (S01–S17)
Rule: every command and its verbatim outcome is recorded here. "It worked" without
output is not evidence.

## Baseline environment (recorded 2026-08-26)

| Item | Value | Evidence |
|---|---|---|
| Host OS | Windows 11 (win32), PowerShell 5.1 | env |
| Working copy | `C:\Users\omare\OneDrive\Desktop\AI` (OneDrive-synced path — flagged RISK for bind-mounts; sites/volumes MUST stay in Docker named volumes, never inside synced folders) | path |
| Docker Desktop | installed, daemon was STOPPED at recovery; started 2026-08-26 ~00:4x; classified BLOCKER-B (engine down, Desktop up) → resolved by normal restart; full evidence in M1_ENVIRONMENT.md | first `docker info` failed (npipe not found); after launch: READY |
| Docker engine | server 29.6.1, WSL2 backend (`wsl --status`: default distro docker-desktop, v2); smoke test `docker run --rm hello-world` PASS 2026-08-26 | command output |
| Repo commit at env creation | `e132671` (= origin/master) | git |

## Vendor tooling pin

| Item | Value |
|---|---|
| frappe_docker clone | `deployment/contec/frappe_docker` (path ignored by parent repo `/*` rule — verified absent from `git status`) |
| Pinned tag | **v3.2.2** (frappe_docker's own versioning; ERPNext version chosen via image refs) |
| Vendor integrity | upstream repo untouched; all Contec customization goes through overrides/apps.json per D-004 |
| ERPNext image pinned by pwd.yml | `frappe/erpnext:v16.31.0` (+ `mariadb:11.8`) — matches D-001 version-16 requirement |

## Gap register (updated as found)

1. **hrms not in pwd.yml** — pwd.yml ships erpnext only. Charter requires Frappe HR v16.
   Resolution path: custom image build via apps.json (frappe+erpnext+hrms@version-16 +
   `contec` skeleton) using frappe_docker `Dockerfile`, or dev-container `bench get-app`.
   Decision before first stack build.
2. Gen-A doc validator fails against frozen Gen-C set (see CRASH_RECOVERY_REPORT addendum) — update or retire during M1.
3. Open operator decisions carried from recovery: dedicated `contec-erp` repository (REPOSITORY_STRATEGY.md); production host sign-off (10_DEPLOYMENT_SPEC §1). Neither blocks staging/M1 work.

## S01 execution record

| Run | Command(s) | Result | Evidence |
|---|---|---|---|
| 1 | `docker build` (frappe_docker layered Containerfile, pinned apps.json, secret token) | **FAIL** | `bench init` → `yarn install` → ESOCKETTIMEDOUT on `ace-builds-1.31.2.tgz` (registry.yarnpkg.com) at ~917s. Build attempted 6 times total across sessions. All failed at identical yarn phase. Root cause: Docker Desktop WSL2 network proxy cannot sustain large yarn downloads. curl inside same container downloads the file in 17s. Full analysis: `M1_BUILD_BLOCKER.md` |
| 2 | NOT EXECUTED (blocked by Run #1 failure) | BLOCKED | — |

Scenarios S02–S17: 0 / 17 executed.

## Build attempt summary (2026-08-26)

| # | Method | Result | Failure |
|---|---|---|---|
| 1 | docker build (attached) | FAIL | yarn ESOCKETTIMEDOUT |
| 2 | docker build (detached) | FAIL | Registry metadata TLS timeout |
| 3 | docker build (retry batch ×4) | FAIL ×4 | Same yarn ESOCKETTIMEDOUT |
| 4 | docker build (direct) | FAIL | yarn ESOCKETTIMEDOUT |
| 5 | docker run + bench init (YARN_HTTP_TIMEOUT=300000) | FAIL | yarn Aborted |
| 6 | docker run + manual yarn install | FAIL | Container died during install |

Auth check: PASS (private repo token valid, public repos don't need auth).
Config check: PASS (apps.json correct, Containerfile unmodified, stage images local).
Network check: PASS for curl, FAIL for yarn inside Docker containers.

```
status: blocked
inputs: { charter: "PLATFORM_BAKEOFF.md", pin: "frappe_docker@v3.2.2", blocker: "NETWORK" }
outputs: { log: "docs/contec/M1_INSTALL_LOG.md", blocker_doc: "docs/contec/M1_BUILD_BLOCKER.md" }
errors: ["yarn ESOCKETTIMEDOUT inside Docker containers on this host — 6 attempts, all failed"]
next_action: "resolve network blocker (different network / yarn offline mirror / cloud build), then retry S01"
owner: "system"
timestamp: "2026-08-26T17:55:00+03:00"
```
