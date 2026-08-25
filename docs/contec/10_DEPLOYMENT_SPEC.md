# 10 — Deployment Specification

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-009, D-013
Cost honesty rule: nothing is claimed free without verified limits.

## 1. Deployment options evaluated

| Option | Verdict | Notes |
|---|---|---|
| A. Existing Contec server/PC | PREFERRED if spec met | min: 4 cores, 8GB RAM, 256GB SSD, UPS + auto-start-on-power, wired internet, physical security |
| B. Free cloud tiers | NOT a production basis | free VM offers (e.g., Oracle-style) have reclamation/availability risk; may be used for STAGING only if limits verified at deploy time |
| C. Low-cost VPS | SANCTIONED FALLBACK | 4–8GB class (Hetzner CX42/CPX21 or regional equivalent), ≈ €8–25/month — REAL cost, owner approval recorded in DECISION_LOG before purchase |

Software licensing remains zero in all options (GPL stack, D-001).

## 2. Production topology

Per 04 §1 diagram: frappe_docker compose project with services
`backend`, `websocket`, `scheduler`, `workers` (short+long), `mariadb`,
`redis-cache`, `redis-queue`, fronted by Caddy (auto-HTTPS via Let's Encrypt;
HTTP→HTTPS redirect; HSTS). Custom image `contec-erp:vN` built from
frappe_docker `Dockerfile` with layers frappe+erpnext+hrms+contec (digest-pinned).

Domain plan: `erp.contec.example` (A record → server/tunnel). If public IP is
impossible on-prem, use Cloudflare Tunnel as front door ONLY; system must stay
operable on LAN if tunnel dies (documented degraded mode, D-013).

## 3. Environment promotion & releases

git tag vX.Y → CI builds image → deploy staging (same host, separate project +
separate DB container + anonymized data copy) → smoke suite (12 §5) green →
prod compose pull+rollout → post-deploy health check script. Rollback = previous
tag redeploy + DB point-in-time restore procedure if migration ran (07 §9 freeze
protects posted data).

## 4. Backup architecture (R12)

| Layer | Mechanism | Schedule |
|---|---|---|
| Logical dump | `bench backup --with-files` inside scheduler sidecar | nightly 01:00 Africa/Cairo |
| Binlog | MariaDB binlogs on volume | continuous (PITR within retention) |
| Files | private/public files volume snapshot | nightly with backup |
| Off-site | rclone crypt → S3-compatible/B2 bucket | nightly after dump, GFS: 7 daily / 4 weekly / 12 monthly |
| Restore drill | scripted restore into scratch compose project + row-count & TB check | weekly (staging), pre-go-live mandatory |

Retention: 90 days minimum on-site, 12 months off-site. Encryption keys live in
owner's password vault AND printed sealed envelope at office safe (documented).
"A backup never restored is not a backup": drill evidence archived per 12 T-OPS.

## 5. Monitoring & logging

- `/api/method/ping` healthcheck + compose healthchecks on all services.
- Uptime probe (external, e.g., UptimeRobot free tier or self-hosted Kuma)
  alerting owner+dev via Telegram/email.
- Logs: docker json-file with rotation (100MB×10); bench logs volume.
- Weekly automated report: backup sizes, restore-drill status, disk usage,
  failed-login count (feeds 11 §5).

## 6. Sizing & performance sanity

8–15 concurrent users, ~2–5k documents/month → 2 vCPU/4GB is functional floor,
4 vCPU/8GB target (Option C mid-tier). Import of 5k-row batch must not degrade
interactive p95 >4s during run (worker queue isolation for long jobs).

## 7. Go-live deployment gate (all mandatory)

[ ] reproducible install from docs on clean host (staging proves it)
[ ] HTTPS valid cert, HTTP redirects, HSTS
[ ] 8+ users created with roles (06), negative permission tests pass
[ ] opening balances loaded and Trial Balance variance = 0 (07 §8)
[ ] core cycle smoke suite green (12 §5)
[ ] nightly backup fired ≥3 consecutive nights; restore drill PASSED
[ ] monitoring alerts delivered to a real phone
[ ] secrets audit clean (11 §4); .env.example has no real values
[ ] rollback tested once (previous tag + PITR dry-run)
[ ] admin runbook + user quick-guides (AR first) published
