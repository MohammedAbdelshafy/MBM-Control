# 04 — Architecture

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-001..D-005, D-013
Platform: ERPNext v16 on Frappe framework, deployed with frappe_docker.

## 1. System context

```
                       ┌──────────────────────────────┐
 Desktop/Tablet/Phone  │  HTTPS (Caddy reverse proxy) │
 (browsers, AR/EN) ───▶│  automatic TLS, rate limit   │
                       └──────────────┬───────────────┘
                                      ▼
        ┌─────────────────────────────────────────────────────────┐
        │              Docker host (Contec server / VPS)          │
        │  ┌───────────────┐   ┌───────────────┐                  │
        │  │ backend       │   │ websocket     │  frappe_docker   │
        │  │ gunicorn x N  │   │ node socketio │  official images │
        │  └──────┬────────┘   └──────┬────────┘                  │
        │         ▼                   ▼                           │
        │  ┌───────────────┐   ┌───────────────┐  ┌────────────┐  │
        │  │ MariaDB 10.6  │   │ Redis cache + │  │ scheduler  │  │
        │  │ site: contec  │   │ Redis queue   │  │ bench worker│ │
        │  └───────────────┘   └───────────────┘  └────────────┘  │
        │                                                         │
        │  Volumes: sites/ (DB data, public+private files, logs)  │
        │  Apps in image: frappe, erpnext, hrms, contec(custom)   │
        └─────────────────────────────────────────────────────────┘
                     │ nightly                        ▲ outbound only
                     ▼                                │
        backup volume → encrypted off-site copy      AI/OCR provider API
        (rclone: S3-compatible or B2) — Phase 2      (suggestions ONLY)
```

Rules:
- Only ports 80/443 exposed. DB/Redis NEVER publicly reachable (D-009).
- All state lives in named volumes → backup = volume-consistent dump + files.
- `contec` custom app carries ALL Contec fixtures/code; zero core edits (D-004).

## 2. Software bill of materials

| Layer | Component | Version pin policy |
|---|---|---|
| OS | Ubuntu LTS on host | current LTS |
| Runtime | Docker Engine + compose plugin | stable channel |
| ERP | erpnext | version-16 branch pin (image digest pinned) |
| Framework | frappe | matching version-16 |
| HR | hrms | version-16 |
| Custom | contec app | repo path `apps/contec/` (this monorepo subdir) |
| DB | MariaDB 10.6 | frappe_docker default (Postgres NOT used for production V1) |
| TLS/proxy | Caddy OR Traefik per frappe_docker docs | digest pinned |

## 3. The `contec` custom app (only place we write code)

```
apps/contec/
  contec/
    hooks.py                 # doc_events, fixtures, scheduler
    contec/doctype/
      contec_contract/       # P2/P6 contract register (non-financial)
      contec_expense_voucher/# petty-cash spend draft (P3/P5)
      contec_document/       # OCR-ready attachment container (P7)
    api/                     # whitelisted methods (mobile entry helpers)
    fixtures/                # roles, tax templates (EG VAT/WHT), CoA, workflows,
                             # letterheads, print formats AR/EN, custom fields
    utils/
      arabic_search.py       # normalization for search (08 §7)
      duplicate_guard.py     # fuzzy duplicate detection (09 §6)
    tests/                   # hermetic pytest + Frappe test records
```

Extension mechanisms used (CONFIGURE→EXTEND→BUILD):
1. Configure: CoA, cost centers, workflows, roles, print formats, tax templates.
2. Extend: Custom Fields via fixtures; server/client scripts versioned in app;
   doc_events hooks for validation/duplicate guard.
3. Build: the three custom DocTypes above — nothing else without new decision.

## 4. Environments

| Env | Host | Purpose | Data |
|---|---|---|---|
| dev | developer machine (frappe_docker dev container) | build/test | synthetic seeds only |
| staging | same prod host, second compose project OR cheap VPS | UAT, restore drills | anonymized copy of prod |
| prod | chosen deployment target (10_DEPLOYMENT_SPEC §2) | live | real |

Promotion path: git tag → image build → staging deploy → smoke suite (12) → prod.

## 5. Integration surface

| Consumer | Mechanism | Constraint |
|---|---|---|
| Mobile browsers | responsive Desk + Quick Entry pages | no native app dependency |
| BI/AI assistants | REST `/api/resource/*` read-only token | token WITHOUT submit/delete scopes (11 §7) |
| OCR (Phase 2) | internal queue job calling provider API | writes suggestions only; human review gate (D-011) |
| Email/WhatsApp share | print format PDF links | no auto-send of financial docs |

## 6. Non-functional targets

- ≤2s p95 page load on 4G for list/form views at 8–15 concurrent users.
- Import 5,000-row supplier-bill batch completes <15 min with row-level errors.
- Nightly backup window <30 min; RPO 24h, RTO 4h (restore drill proves it).
- Availability target: business-hours 99% (single-host reality, documented).
