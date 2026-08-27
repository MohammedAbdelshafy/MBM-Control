# M1 BUILD BLOCKER — Custom Image Build

**Status**: BLOCKED
**Date**: 2026-08-26
**Author**: MiMo-V2.5 Worker
**Classification**: NETWORK BLOCK

## ROOT CAUSE

`yarn install --check-files` (called by `bench init` inside the Docker build) consistently fails with `ESOCKETTIMEDOUT` on `registry.yarnpkg.com` when downloading large tarballs (specifically `ace-builds-1.31.2.tgz`, 9.3 MB). This happens inside Docker containers on this host (Windows 11, Docker Desktop 4.80.0, WSL2 backend).

**Critical diagnostic**: `curl` inside the same container CAN download the same file in 17 seconds. The failure is specific to yarn's HTTP client mechanism inside the Docker network layer, not a general connectivity issue.

## EVIDENCE

| Attempt | Method | Result | Failure Point | Duration |
|---|---|---|---|---|
| 1 | `docker build` (attached) | FAIL | yarn ESOCKETTIMEDOUT (ace-builds) | ~917s |
| 2 | `docker build` (detached) | FAIL | Registry metadata TLS timeout | ~5s |
| 3 | `docker build` (retry batch ×4) | FAIL ×4 | Same yarn ESOCKETTIMEDOUT | ~20min each |
| 4 | `docker build` (direct) | FAIL | yarn ESOCKETTIMEDOUT (ace-builds) | ~917s |
| 5 | `docker run` + `bench init` (YARN_HTTP_TIMEOUT=300000) | FAIL | Same yarn error (Aborted) | ~1395s |
| 6 | `docker run` + manual `yarn install` | FAIL | Container died during install | ~2h |

## NETWORK RESULTS

| Test | Result | Latency |
|---|---|---|
| Docker Hub (hello-world pull) | PASS | ~2s |
| Docker Hub (frappe/base:v16.31.0 pull) | PASS | ~20min (slow but complete) |
| Docker Hub (frappe/build:v16.31.0 pull) | PASS | ~20min |
| Docker Hub (frappe/hrms:v16.16.0 pull) | FAIL | "docker login" error (rate limit or tag issue) |
| yarnpkg.com HEAD (pug-error 9KB) | PASS | 2s |
| yarnpkg.com curl (ace-builds 9.3MB) | PASS | 17s |
| yarnpkg.com yarn install (ace-builds) | FAIL | ESOCKETTIMEDOUT at ~917s |
| GitHub API | PASS | ~1s |
| npm registry | PASS | ~1s |

## CONFIG RESULTS

- `apps.json`: CORRECT (erpnext@v16.32.3, hrms@v16.16.0, contec@v0.1.0-m1)
- Containerfile: OFFICIAL (frappe_docker images/layered/Containerfile, unmodified)
- Stage images: LOCAL (frappe/build:v16.31.0, frappe/base:v16.31.0)
- Build args: CORRECT (FRAPPE_PATH, FRAPPE_BRANCH, secret apps_json)

## AUTH RESULTS

| Check | Result |
|---|---|
| Private repo token in apps.json | PASS (gho_ token embedded, repo is private) |
| Public repos (erpnext, hrms) | PASS (no auth needed) |
| Token validity | UNKNOWN (build died before reaching app fetch phase) |

## VERSION RESULTS

| Component | Version | Source | Status |
|---|---|---|---|
| ERPNext | v16.32.3 | apps.json pinned | CORRECT |
| Frappe | v16.31.0 | FRAPPE_BRANCH arg | CORRECT |
| HRMS | v16.16.0 | apps.json pinned | CORRECT (but not fetched — build dies before) |
| Contec | v0.1.0-m1 | apps.json pinned | CORRECT (but not fetched — build dies before) |
| frappe_docker | v3.2.2 | git tag | CORRECT |

## WHAT CHANGED

- 6 build attempts documented
- Temp secret file created at `%TEMP%\contec_apps.json` (tokenized, needs cleanup)
- Build retry batch created at `C:\Users\omare\contec-build-retry.cmd`
- Builder containers created/destroyed (no persistent state)

## WHAT DID NOT CHANGE

- Vendor Containerfile: UNTOUCHED
- Vendor source (frappe/erpnext/hrms): UNTOUCHED
- Recovered running stack: PRESERVED (7 containers Up)
- DECISION_LOG: UNCHANGED
- Accounting logic: NONE
- Business data: NONE
- Unrelated MBM/clipping files: UNTOUCHED

## SAFE OPTIONS

| Option | Description | Risk | Reproducibility |
|---|---|---|---|
| A. Retry on different network | Connect from a different network (mobile hotspot, VPN, different ISP) | Low | HIGH (same official mechanism) |
| B. Pre-cache yarn offline mirror | Download all frappe yarn deps on host, mount as offline mirror into build | Low (no vendor modification) | HIGH |
| C. In-place stack upgrade | `bench get-app` hrms + contec inside recovered running stack | Medium (modifies running stack) | LOW (not from clean state) |
| D. Dev container approach | Run bench init + get-app inside a frappe/build container, export as image | Medium | MEDIUM (manual steps) |
| E. Use a cloud build environment | Build the image on a cloud VM with better networking | Low | HIGH |

## RECOMMENDED NEXT ACTION

**Option A** (try different network) is the lowest-risk path that preserves full reproducibility. If unavailable, **Option B** (yarn offline mirror) is the next-best — it doesn't modify vendor source, only pre-populates a cache that yarn already supports.

**Option C** (in-place upgrade) is explicitly NOT recommended as the first choice per the mission directive. If chosen, it requires a D-019 deviation entry in DECISION_LOG before implementation.

## CLASSIFICATION

**NETWORK BLOCK** — Docker Desktop WSL2 network proxy cannot sustain the large sequential HTTP downloads that yarn requires during `bench init`. The host CAN reach the registry (curl works), but yarn's HTTP client mechanism fails under the Docker network layer.
