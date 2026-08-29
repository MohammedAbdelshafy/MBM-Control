# CONTEC — LINUX HOSTING BAKE-OFF 2026
# VPS / Backup Provider Comparison & Recommendation

**Status:** RESEARCH & PLANNING COMPLETE — Phase 0 Final Gate APPROVED (2026-08-29)
**Date:** 2026-08-29
**Author:** Nemotron 3 Ultra / OpenCode
**Purpose:** Evidence-based provider comparison to host the Contec ERP runtime on Linux,
so M1 (S01–S17) is unblocked and the future production deployment has a chosen home.

**SCOPE GOVERNANCE**
- RESEARCH/VERIFICATION ONLY. No purchase, no account creation, no deployment, no provisioning.
- Do NOT purchase the server. Do NOT provision the server. Do NOT deploy anything.
- Do NOT modify Windows Docker. Do NOT touch either Docker VHDX (`docker_data.vhdx`).
- Do NOT modify Contec application code.
- Windows Docker (`docker_data.vhdx` 103.8 GB) and all Contec code remain UNTOUCHED.
- Decision requires OWNER approval before any spend/commit.
- All prices are freshly researched 2026 list prices and are subject to change at checkout.

**EVIDENCE CLASSIFICATION — HOW TO READ THIS DOCUMENT**
- **VERIFIED FACT:** checked against official source/repository metadata on 2026-08-29 (e.g. GitHub releases, hetzner.com, local `pwd.yml` / `pyproject.toml`).
- **ESTIMATE:** derived calculation or market figure that varies by region/currency/VAT/term (e.g. latency, monthly totals).
- **PROPOSAL:** recommended choice that still requires owner approval before spend.
- **UNKNOWN:** cannot be known until provisioning / owner decision (e.g. exact region availability at order time, final domain, retention policy).

---

## 1. EXECUTIVE DECISION

**RECOMMENDED CONTEC HOST [PROPOSAL, price = VERIFIED FACT]: Hetzner Cloud — CX33 (4 vCPU / 8 GB RAM / 80 GB NVMe), region Falkenstein or Nuremberg (Germany), subject to actual availability at provisioning [UNKNOWN at order time].**

- **Current verified price [VERIFIED FACT, 2026-08-29]: €8.49/month** (net, ex-VAT, Falkenstein/Nuremberg; via hetzner.com / docs.hetzner.com June 2026 price adjustment; costgoat/comparedge Aug 2026 trackers). **ESTIMATE** for continuous stack incl. backups/domain: ~€10–11/month (see §7).

Rationale in one line: **best balance of modern hardware, sub-minute provisioning,
Rock-solid Linux/Docker story, 20 TB traffic, and an EU region with ~80–100 ms latency to Cairo [ESTIMATE] at a production-credible price.**

**Version pins harmonized to Phase 0 Final Gate [VERIFIED FACT]:**
- **ERPNext: v16.32.3** — `frappe/erpnext:v16.32.3` (GitHub `frappe/erpnext` releases: v16.33.0 is latest but has a breaking change; v16.32.3 is last mature patch-stable and is the exact image proven running on the host per `M1_ENVIRONMENT.md` addendum line 75). Runbook `v16.31.0` is stale (2 patches behind) — do NOT use v16.31.0 merely because the local `pwd.yml` says so.
- **Frappe Framework:** bundled `version-16` inside the v16.32.3 image (requires Python ≥3.14 / Node ≥24 — handled by official image) [VERIFIED FACT].
- **Frappe HR / HRMS: v16.16.0** — `version-16` branch (GitHub `frappe/hrms` releases: v16.16.0 = 2026-08-07 mature; v16.17.0 = 2026-08-28 fresh; v16.16.0 matches the M1 reference environment) [VERIFIED FACT].
- **Contec custom app: v0.1.0-m1** — repo `apps/contec/pyproject.toml` / `contec/__init__.py` = `0.1.0` [VERIFIED FACT].
- **MariaDB: 11.8** (`mariadb:11.8` as in `pwd.yml`) [VERIFIED FACT]; **Redis: 6.2-alpine** [VERIFIED FACT].
- **frappe_docker tooling: v3.2.2** (pristine clone) [VERIFIED FACT].

CX lineage correction [VERIFIED FACT]: **CX32 is deprecated** (vpsfor.dev 2026-07-11; Hetzner docs). Its direct replacement is **CX33 (4v/8G/80G, €8.49)**. Earlier `M1_LINUX_RUNTIME_OPTIONS.md` mislabeled the Hetzner "CX42 (4 vCPU / 8 GB)" tier; the current Hetzner shared line is: CX22/CX23 (2/4), **CX33 (4/8) ← recommended [PROPOSAL]**, CX43 (8/16), CX53 (16/32). Contabo/Vultr/OVH naming unchanged.

**Shortlist produced in this document (see §7) [PROPOSAL]:**
1. **#1 BEST VALUE (Recommended):** Hetzner **CX33** (4v/8G/80G, €8.49) ⭐
2. **#2 BEST CHEAP:** Hetzner CX22/CX23 (2v/4G/40G, ~€3.79–5.49) or Contabo Cloud VPS 4 for raw RAM per euro
3. **#3 BEST FREE / ALMOST FREE:** Oracle Always Free A1 (2 OCPU / 12 GB) — caveat-heavy
4. **#4 BEST RELIABILITY:** OVHcloud VPS-1 / DigitalOcean Basic
5. **#5 BEST FUTURE SCALE:** Hetzner **CX43** (8v/16G/160G, €15.99)

---

## 2. RESOURCE REQUIREMENT (~10 USERS)

ERPNext v16.32.3 + Frappe HR v16.16.0 + custom `contec` v0.1.0-m1, ~10 concurrent users, self-hosted, single site.

| Workload profile | RAM | vCPU | NVMe | Notes | Class |
|---|---|---|---|---|---|
| **Dev / M1 bake-off / staging** | 4 GB | 2 | 40 GB | Enough to install and run S01–S17 | ESTIMATE |
| **Recommended baseline (~10 users)** | **8 GB** | **4** | **80 GB** | Fits MariaDB + 3× Redis + web workers + scheduler with headroom; see caveat below | PROPOSAL + ESTIMATE |
| Production + heavy reporting | 16 GB | 8 | 160 GB | Scale-up later, no lock-in (one-click upgrade on Hetzner) | ESTIMATE |

**Storage-headroom caveat [VERIFIED FACT + ESTIMATE]: 80 GB is NOT universally sufficient.** Adequacy depends on OS (~4–6 GB) + Docker images (~8–10 GB) + build layers (~6–10 GB during build) + site volumes (DB + files/attachments, tens of GB growing) + logs/temp + restore headroom (staging a full restore needs ~1× data). For ~10 users starting fresh, **80 GB (CX33) is adequate [ESTIMATE] provided** backups stream off-box to B2 (not local disk), build layers are pruned after first build, and free space is monitored — but it is not a universal guarantee. Comfort margin is 160 GB (CX43). Do NOT state 80 GB suffices for all futures.

| Sizing | NVMe | When |
|---|---|---|
| **MINIMUM** | 40 GB | Dev / M1 only, no attachment growth, no local restore staging |
| **RECOMMENDED** | **80 GB** | ~10 users year-one with off-box B2 backups and monitoring (the CX33 plan) |
| **COMFORTABLE** | 160 GB | Heavy attachments / local restore staging / long retention on-box |

**RAM gate [ESTIMATE + PROPOSAL]:** 4 GB = tight/risky (scheduler + workers + DB + Redis contend); **8 GB = healthy floor for ~10 users [PROPOSAL]**; 16 GB = not justified at day-one. Choose **8 GB / 4 vCPU** — this is the CX33.

---

## 3. PROVIDER COMPARISON (fresh 2026 list prices)

Prices are monthly list/general-market figures [ESTIMATE]; final bill varies by region, currency, VAT, and term. Hetzner CX33 price is **VERIFIED FACT**; all others are **ESTIMATES** from 2026 trackers.

| Provider | ~4 GB tier | ~8 GB tier | ~16 GB tier | Bandwidth | Notes (2026) | Class |
|---|---|---|---|---|---|---|
| **Hetzner** | CX22/CX23 2v/4G/40G **~€3.79–5.49** | **CX33 4v/8G/80G €8.49** ⭐ [VERIFIED FACT] | CX43 8v/16G/160G **€15.99** | 20 TB | CX32 deprecated → CX33 is replacement. April/June 2026 price adjustment (+30–38% on higher tiers). Sub-minute provisioning, modern Intel/EPYC. | VERIFIED (CX33) / ESTIMATE (others) |
| **Contabo** | — | Cloud VPS 4: 4v/8G/100G **€4.40–5.28** (best RAM/€) | Cloud VPS 6: 6v/12G/200G ~€6–7 | Unlimited (FUP) | Cheapest raw specs; older shared Xeon; provisioning can take hours. | ESTIMATE |
| **OVHcloud** | VPS-1: 4v/8G/75G ~€6.46–6.49 | VPS-2: 6v/12G/100G ~€8.50–9.99 | VPS-3: 8v/24G/200G ~€12.75–19.97 | Unlimited | Anti-DDoS + daily backup included. Mar 2026 price rise (~9–30%). | ESTIMATE |
| **DigitalOcean** | s-2vcpu-4gb **$24** | s-4vcpu-8gb **$48** | s-8vcpu-16gb **$96** | 4–6 TB | Premium per-GB; great UX; $200/60-day credit for new accounts. | ESTIMATE |
| **Vultr** | Regular 4GB **$20** | Regular 8GB **$40** | Regular 16GB **$80** | 3–5 TB | Tel Aviv region = sub-30 ms to Cairo (best MENA latency). | ESTIMATE |
| **Oracle (free)** | A1 2 OCPU/12 GB **$0** | (same pool) | (same pool) | 10 TB | See §8 for major 2026 caveats. | ESTIMATE |

Vendor of note for Egypt latency [ESTIMATE]:
- **Kamatera** (Tel Aviv DC): ~sub-30 ms to Cairo, from ~$4/mo — the best latency option.
- **Vultr** (Tel Aviv region): sub-30 ms to Cairo, $6/mo entry.
- **LightNode** has a hardware data center inside Cairo (~$7.71/mo) — only mainstream option with an EG IP.
- EU regions (Frankfurt/Falkenstein/Nuremberg/Helsinki/Warsaw) run **~80–100 ms** to Cairo — fine for a non-realtime ERP UI.

---

## 4. REGION COMPARISON (Latency to Cairo / Egypt) [ESTIMATE]

| Region | Approx. Cairo latency | Notes | Class |
|---|---|---|---|
| Tel Aviv (Kamatera / Vultr) | <30 ms | Best MENA latency, but geo-politics / data-residency not EU | ESTIMATE |
| Frankfurt / Falkenstein / Nuremberg | ~60–100 ms | Good peering via Telecom Egypt Mediterranean cables; EU/GDPR | ESTIMATE |
| Helsinki (Hetzner) | ~80–110 ms | EU/GDPR, further north | ESTIMATE |
| Warsaw (OVHcloud PL) | ~80–110 ms | EU/GDPR, good east-Europe peering | ESTIMATE |
| Cairo (LightNode) | <10 ms | Only in-country option; higher cost, smaller provider | ESTIMATE |

**Recommendation [PROPOSAL]:** For an Egyptian ERP with EU data-sovereignty comfort, **Germany (Frankfurt/Falkenstein/Nuremberg)
is the sweet spot** — GDPR, reliable peering, ~80–100 ms which is imperceptible for a web ERP.
Tel Aviv regions are the fallback if sub-30 ms becomes a hard requirement. **Actual region at provisioning is UNKNOWN until order time** — Falkenstein / Nuremberg subject to availability.

---

## 5. BACKUP COMPARISON (object storage, S3-compatible)

For off-site database + files backups (`bench backup --with-files` → encrypted archive → rclone to object storage).

| Provider | Storage/GB-mo | Egress | Min. billing | Notes | Class |
|---|---|---|---|---|---|
| **Backblaze B2** | **$0.00695/GB ($6.95/TB)** [VERIFIED FACT, Aug 2026] | Free up to 3× storage, then $0.01/GB; **free via Cloudflare CDN** | None (10 GB free tier) | Recommended for backup/archive: cheapest raw storage, no min. bill. ⭐ | VERIFIED |
| Wasabi | ~$7.99/TB | Free (fair-use ≤1:1) | **1 TB min ($7.99/mo)** + 90-day retention | Cheaper only at scale; 1 TB min wastes money for small backups | ESTIMATE |
| Cloudflare R2 | $0.015/GB (std) / $0.01 (infrequent) | $0 (all egress) | None (10 GB free tier) | Best if you also serve files; higher storage than B2 | ESTIMATE |
| AWS S3 | ~$0.023/GB | ~$0.09/GB | None | Expensive egress; overkill | ESTIMATE |
| Contabo Object Storage | €2.49/250 GB, €9.96/1 TB | (regional) | None | Cheap, but keep B2 as primary recommendation | ESTIMATE |
| Hetzner Snapshots | **€0.012–0.0143/GB** [VERIFIED FACT, Hetzner docs] | — | None | Crash-consistent disk image; complements B2 (not a replacement) | VERIFIED |

**Recommendation [PROPOSAL]:** **Backblaze B2** with **rclone** for encrypted snapshots.
Cost at current B2 list price [ESTIMATE, pay-as-you-go, first 10 GB free]:
- 100 GB → **~$0.63/mo** (90 GB billable at $0.00695)
- 250 GB → **~$1.74/mo**
- 500 GB → **~$3.48/mo**
For ~10 users the monthly Contec database + files are small (tens of GB) initially; B2 cost is negligible. Alternative: **Cloudflare R2** is ~2× storage cost (100 GB ~$1.50) but $0 egress — choose only if egress-heavy.

**Restore drill [GOVERNANCE]: BACKUP IS NOT VALID UNTIL RESTORE-TESTED.** No backup may be claimed as valid until a documented restore (B2 → fresh volume → `bench restore` → hash-verify → site smoke test) has succeeded. Schedule per `10_DEPLOYMENT_SPEC` and backup-disaster-recovery skill.

---

## 6. SECURITY

Same posture as `M1_LINUX_RUNTIME_OPTIONS.md §8` [PROPOSAL, implementation-time]:
- SSH key-only auth, root login disabled, UFW allow 22/80/443 from admin IPs.
- Docker: root-owned socket; never expose TCP without mTLS.
- MariaDB + Redis bound to localhost / Docker-internal network only.
- unattended-upgrades, fail2ban optional, daily backup + off-site copy + periodic restore drill.
- Contec specifics: named accounts only, TOTP MFA (Frappe built-in), RBAC, audit logging,
  private file storage, API guard hook (D-011). AI/OCR remains SUGGESTION-ONLY (never posts/approves/executes).

---

## 7. SHORTLIST & FINAL MONTHLY COST

### Shortlist [PROPOSAL]

| Rank | Provider / Plan | Specs | Monthly | Why | Class |
|---|---|---|---|---|---|
| **#1 BEST VALUE** ⭐ | **Hetzner CX33** | 4v/8G/80G NVMe, 20 TB | **€8.49** [VERIFIED FACT] | Modern hardware, sub-minute provisioning, EU region, easy scale-up | VERIFIED (price) / PROPOSAL (choice) |
| #2 BEST CHEAP | Hetzner CX22/CX23 | 2v/4G/40G, 20 TB | **~€3.79–5.49** | Cheapest production-credible box | ESTIMATE |
| #2 alt RAW SPECS | Contabo Cloud VPS 4 | 4v/8G/100G, unlimited | **€4.40–5.28** | Most RAM/€ (older shared Xeon, slower provisioning) | ESTIMATE |
| #3 BEST FREE/ALMOST | Oracle Always Free A1 | 2 OCPU/12 GB | **$0** | See big caveats below (§8) | ESTIMATE |
| #4 BEST RELIABILITY | OVHcloud VPS-1 | 4v/8G/75G, unlimited | **~$6.46–6.49** | Anti-DDoS + daily backup included; slower support | ESTIMATE |
| #5 BEST FUTURE SCALE | Hetzner **CX43** | 8v/16G/160G | **€15.99** [VERIFIED FACT] | Two-step scale path if needs grow | VERIFIED (price) / PROPOSAL (scale) |

### Recommended Contec stack monthly cost (Hetzner CX33 baseline) [ESTIMATE]

| Item | Monthly | Class |
|---|---|---|
| VPS Hetzner **CX33** (8 GB / 4 vCPU / 80 GB, incl. 20 TB) | **€8.49** | **VERIFIED FACT** |
| Hetzner snapshots (€0.012–0.0143/GB, e.g. 1×80 GB image) | ~€0.96–1.15 | ESTIMATE |
| Off-site Backblaze B2 (rclone, e.g. 100–250 GB retained) | ~$0.63–1.74 (~€0.58–1.60) | ESTIMATE |
| Domain (erp.contec.example, e.g. ~€10–15/yr) | ~€1.00–1.25 | ESTIMATE |
| **TOTAL Continuous** | **~€10.50–12.50/month (~$11–14)** | **ESTIMATE** |
| **One-time setup** | ~€0 (self-managed) | ESTIMATE |

> LOW / EXPECTED / HIGH framing [ESTIMATE]: **LOW ~€9.50** (CX33 + light B2, no snapshots), **EXPECTED ~€11** (above table), **HIGH ~€18–20** (CX43 8v/16G/160G + heavier retention). Final checkout varies by VAT/currency/region [UNKNOWN until invoice].

---

## 8. ZERO-COST OPTIONS (with honest caveats)

### Oracle Cloud Always Free — $0/mo but fragile
- **2026 CHANGE (enforced Aug 18, 2026) [VERIFIED FACT]:** Ampere A1 ARM cut from **4 OCPU/24 GB → 2 OCPU/12 GB**.
  Tenancy-wide pool; instances over the limit are **auto-terminated**. No reliable notification.
- Persistent ARM **capacity shortages** — creating/resizing A1 instances often fails ("out of host capacity").
- Runs **ARM64**, not x86. Frappe/ERPNext and the pinned `mariadb:11.8`/`redis:6.2` images do run on ARM,
  but this **deviates from the x86 `frappe_docker` reference** used everywhere else and adds an undocumented host.
- Vendor can change/remove the free tier again at any time — violates the "no fragile runtime" lesson that made us leave Docker Desktop.
- **Verdict [PROPOSAL]:** usable only for a throwaway dev sandbox (never authoritative money data). Not recommended for Contec. Marked as such.

### DigitalOcean / Vultr free credits
- **DigitalOcean:** $200 credit for new accounts, **expires in 60 days** — fine for an M1 trial, not a permanent home.
- **Vultr:** approval-based free tier; limited.

### Kamatera trial / LightNode (in-country)
- Kamatera offers pay-per-use from ~$4 with Tel Aviv latency; not free but cheap.
- LightNode offers a **Cairo** option (~$7.71/mo) if an Egyptian IP is non-negotiable.

---

## 9. RISKS

| Risk | Mitigation | Class |
|---|---|---|
| Provider price changes (2026 DRAM/NVMe-driven inflation is real) | Prefer Hetzner (transparent, generous base); budget +€1–3 headroom; avoid long lock-in without discount | ESTIMATE |
| Latency to Cairo 80–100 ms from Germany | Acceptable for ERP UI; validate with a ping test before committing; Tel Aviv/Vultr/Kamatera fallback if not | ESTIMATE |
| Oracle free-tier fragility / auto-termination | Not chosen for Contec; only a dev sandbox at most | VERIFIED FACT |
| VPS is a single point of failure | Off-site encrypted backups (B2) + documented restore; later add a second region/mirror if needed. **BACKUP IS NOT VALID UNTIL RESTORE-TESTED.** | PROPOSAL |
| Unmanaged host = self-admin burden | Document runbooks; SSH keys; unattended-upgrades; snapshots before any change | PROPOSAL |
| Cost creep (scale-up, snapshots, egress) | Set Hetzner budget alerts; track snapshots; B2 egress within free 3× | ESTIMATE |
| 80 GB proves tight (heavy attachments / local restore staging) | Monitor free space; prune build layers; stream backups off-box; scale to CX43 160 GB if needed | ESTIMATE |

---

## 10. UNKNOWNS / REQUIRES OWNER DECISION [UNKNOWN]

- Domain name to register (e.g. `erp.contec.<tld>`) — TBD.
- Whether to start dev/staging on Hetzner CX22/CX23 (cheapest) and only bump to **CX33** for prod — owner call.
- Backup retention policy (keep N daily/weekly/monthly B2 snapshots).
- Preferred region if sub-30 ms to Cairo becomes a hard requirement (Vultr/Kamatera Tel Aviv vs LightNode Cairo).
- Exact Hetzner region at order time — **Falkenstein / Nuremberg subject to actual availability at provisioning**.
- Whether to stand up the M1 bake-off on the free Oracle sandbox vs the recommended paid **CX33** (recommended: paid, for stability).
- Go / no-go authorization to purchase (Hetzner + domain + B2 account).

---

## 11. RECOMMENDED PLAN (summary)

1. **Compute [PROPOSAL]:** Hetzner Cloud **CX33** (4 vCPU / 8 GB RAM / 80 GB NVMe), Ubuntu 24.04 LTS, region **Falkenstein or Nuremberg — subject to actual availability at provisioning [UNKNOWN]**.
2. **Runtime [VERIFIED FACT]:** Docker Engine (native) + official **frappe_docker** (`frappe/erpnext:v16.32.3` + `mariadb:11.8` + `redis:6.2-alpine`).
3. **Apps [VERIFIED FACT]:** **ERPNext v16.32.3** + **Frappe HR v16.16.0** + custom **`contec` v0.1.0-m1** (pulled from GitHub via `apps.json` custom image build), no vendor-core edits.
4. **Backups [PROPOSAL]:** provider snapshots + **Backblaze B2** via rclone (encrypted, off-site) + scheduled restore drill. **BACKUP IS NOT VALID UNTIL RESTORE-TESTED.**
5. **HTTPS [PROPOSAL]:** Caddy/Traefik + Let's Encrypt in front of the nginx service.
6. **Monthly continuous cost [ESTIMATE]:** **~€10.50–12.50 (~$11–14)**; one-time setup ~€0. **Verified base: CX33 €8.49.**
7. **Next single action (after owner approval) [PROPOSAL]:** purchase Hetzner **CX33** + register domain + open B2 → then execute the
   migration sequence in `LINUX_DEPLOYMENT_PLAN.md`.

---

## 12. EVIDENCE / SOURCES (2026)

1. Hetzner Cloud shared vCPU plans — **CX33 4v/8G/80G €8.49**, CX22/CX23 ~€3.79–5.49, CX43 €15.99 — hetzner.com/cloud, docs.hetzner.com (June 2026 price adjustment) [VERIFIED FACT]
2. CX32 deprecated → CX33 replacement — vpsfor.dev (2026-07-11), costgoat (2026-08-02), comparedge (2026-07-08) [VERIFIED FACT]
3. Hetzner 2026 price-adjustment detail (40 GB snapshots €0.012–0.0143/GB, backups 20%, CX33 €8.49) — docs.hetzner.com, cloudtally.eu (2026-03-02) [VERIFIED FACT]
4. Contabo official pricing (Cloud VPS 4: 4v/8G/100G €4.40–5.28; unlimited traffic) — contabo.com [ESTIMATE]
5. DigitalOcean Droplet pricing (Basic s-2vcpu-4gb $24, s-4vcpu-8gb $48; $200/60-day credit) — digitalocean.com [ESTIMATE]
6. Vultr Cloud Compute pricing (Regular 4GB $20, 8GB $40; Tel Aviv region) — vultr.com [ESTIMATE]
7. OVHcloud VPS pricing (VPS-1 ~$6.46–6.49, VPS-2 ~$8.50–9.99; Mar 2026 price rise) — ovhcloud.com [ESTIMATE]
8. Oracle Always Free A1 reduced to 2 OCPU/12 GB, enforced 2026-08-18, capacity shortages — oracle.com, terminalbytes, linuxiac [VERIFIED FACT]
9. Backblaze B2 pricing — **$0.00695/GB ($6.95/TB), first 10 GB free, free egress 3× then $0.01/GB, free via Cloudflare CDN** — backblaze.com/pricing (Aug 2026) [VERIFIED FACT]; Wasabi $7.99/TB 1 TB min, R2 $0.015/GB [ESTIMATE]
10. Egypt VPS latency (Tel Aviv <30 ms vs Frankfurt/EU ~80–100 ms; LightNode Cairo) — howtohosting.guide Egypt [ESTIMATE]
11. Contec evidence: `docs/contec/10_DEPLOYMENT_SPEC.md`, `M1_LINUX_RUNTIME_OPTIONS.md`, local `deployment/contec/frappe_docker/pwd.yml` (`v16.31.0` stale), `apps/contec/pyproject.toml` (`0.1.0`) [VERIFIED FACT]
12. Official ERPNext releases — **v16.33.0 latest (2026-08-25, breaking change), v16.32.3 (2026-08-18) recommended**, v16.31.0 stale — github.com/frappe/erpnext/releases [VERIFIED FACT]
13. Official HRMS releases — **v16.17.0 latest (2026-08-28), v16.16.0 (2026-08-07) recommended** — github.com/frappe/hrms/releases [VERIFIED FACT]

---

*Status: RESEARCH & PLANNING COMPLETE. Phase 0 Final Gate APPROVED (2026-08-29). No purchase, no account, no deployment, no provisioning performed. No Windows Docker or VHDX touched. No Contec code modified. Awaiting owner authorization to execute Phase 0.*
