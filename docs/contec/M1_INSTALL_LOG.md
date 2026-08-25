# M1 INSTALL LOG — Reproducible Environment (S01 evidence)

Status: IN PROGRESS · Executor: OX ALPHA · Charter: PLATFORM_BAKEOFF.md (S01–S17)
Rule: every command and its verbatim outcome is recorded here. "It worked" without
output is not evidence.

## Baseline environment (recorded 2026-08-26)

| Item | Value | Evidence |
|---|---|---|
| Host OS | Windows 11 (win32), PowerShell 5.1 | env |
| Working copy | `C:\Users\omare\OneDrive\Desktop\AI` (OneDrive-synced path — flagged RISK for bind-mounts; sites/volumes MUST stay in Docker named volumes, never inside synced folders) | path |
| Docker Desktop | installed, daemon was STOPPED at recovery; started 2026-08-26 ~00:4x | first `docker info` failed (npipe not found); after launch: READY |
| Docker engine | server 29.6.1, WSL2 backend (`wsl --status`: default distro docker-desktop, v2) | command output |
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
| 1 | PENDING | NOT EXECUTED | — |
| 2 | PENDING | NOT EXECUTED | — |

Scenarios S02–S17: 0 / 17 executed.

```
status: in_progress
inputs: { charter: "PLATFORM_BAKEOFF.md", pin: "frappe_docker@v3.2.2" }
outputs: { log: "docs/contec/M1_INSTALL_LOG.md" }
errors: []
next_action: "decide hrms delivery path (custom image vs devcontainer), then execute S01 run #1 verbatim"
owner: "system"
timestamp: "2026-08-26T01:05:00+03:00"
```
