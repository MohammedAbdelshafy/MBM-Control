# 11 — Security Specification

Status: APPROVED (Terminal 1) · Date: 2026-08-25 · Decisions: D-008..D-012
Posture: least privilege, human accountability for money movement, auditable.

## 1. Identity & authentication

- Named accounts only; NO shared logins. Password policy ≥12 chars via
  system settings + rate-limited login (platform defaults tuned).
- MFA: TOTP enabled MANDATORY for OWNER, GM, CHIEF_ACCOUNTANT, SYSTEM_ADMIN;
  optional others (platform supports TOTP).
- Sessions: 8h idle timeout office, remember-device off for privileged roles.
- Developer/owner admin actions performed under named admin account, never
  root-in-app; `Administrator` password sealed in vault + envelope (10 §4).

## 2. Authorization

- Role matrix 06 is the single source of truth; implemented via DocType perms +
  User Permissions + Workflows. Server-side only trust: client hiding is never
  a control.
- User Permission scoping enforced for lists AND reports AND API (06 §4).
- Quarterly access review checklist (owner+chief sign a printed/exported
  role-membership report).

## 3. Financial-integrity controls

- Submit/cancel rights per 06 §2; Journal Entry single-keyholder rule (I2).
- Maker-checker workflow transitions with reviewer ≠ creator condition (WF-1..4).
- API/AI posting prohibition guard hook (07 §10) — default OFF flag per env.
- Frozen periods post-close (07 §9); unfreeze events logged and reviewed.

## 4. Secrets management

- No secrets in git, ever (pre-commit gitleaks in CI; repo history scrub policy).
- Runtime secrets in untracked `.env` on host (chmod 600) or Docker secrets;
  `.env.example` carries placeholders only.
- Inventory of secrets: DB passwords, redis (bound to internal net, no auth
  bypass), TLS account, backup bucket keys, rclone crypt key, AI provider key,
  SMTP creds, Telegram alert token. Each has owner + rotation date (90–180d).

## 5. Network & platform hardening

- Exposed surface: 80/443 only (Caddy). DB/Redis bound to compose network.
- UFW: allow 80/443 (+SSH from admin IPs/key-only, no password SSH).
- Automatic security patches unattended-upgrades (OS); monthly image rebuild to
  pull patched base layers; erpnext/frappe security advisories subscribed.
- Caddy: HSTS, modern TLS only, request body limit 20MB, basic rate limit.
- Login/failed-login audit reviewed weekly (automated report 10 §5).

## 6. Data protection

- Attachments: financial docs in PRIVATE files; direct URL access requires
  auth (platform private-file behavior verified at implementation test T-SEC-6).
- PII minimization: employee national ID stored only if legally required;
  otherwise employee code. Customer/supplier tax IDs stored for invoicing.
- Backups encrypted client-side before leaving site (10 §4).
- Deletion policy: business records are cancelled, never deleted (05 §6);
  physical file deletion only via documented retention job after N years.

## 7. AI & integration safety (Phase 8 alignment)

| Control | Rule |
|---|---|
| AI read scope | dedicated read-only API key, scoped User Permissions, no export of attachments unless task-approved |
| AI write scope | suggestion fields on drafts ONLY (`extraction_json`, `ai_note`) — enforced by field-level permset + hook |
| Prohibited | posting, approving, permission change, delete, alter submitted docs, tax filing — hard list in D-011 |
| Auditability | every AI-originated suggestion stores provider, model, prompt-hash, timestamp in Contec Document |

## 8. Vulnerability & incident process

- Monthly: review Frappe/ERPNext security advisories + dependency scan of the
  custom image (trivy optional but recommended).
- Incident runbook: suspect compromise → disable logins → snapshot volumes →
  rotate all §4 secrets → restore from known-good if integrity doubted →
  post-mortem appended to DECISION_LOG.md.
