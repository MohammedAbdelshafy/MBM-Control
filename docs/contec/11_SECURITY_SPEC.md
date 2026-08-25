# 11 — Security Specification

Status: PROPOSED principles ADOPTED from directive/OX-Alpha rules; controls verification pending implementation
Owner: Terminal 2 (security) 
Last updated: 2026-08-25

## S1. Identity & access

- Authentication mandatory on every non-static route from first deployment.
- Passwords: hashed by the platform with a modern KDF (bcrypt/argon2 class);
  plaintext passwords never stored, logged, or committed. Placeholder/test
  users only in non-production environments.
- Sessions: secure cookies (Secure/HttpOnly/SameSite), timeout on idle,
  logout invalidates server-side session where platform supports it.
- RBAC least privilege per doc 06; permission checks enforced SERVER-SIDE.
- Administrator privileges restricted to designated admins; admin actions
  audited. Nobody works daily as Administrator.
- Account recovery: defined strategy [PROPOSAL: admin-initiated reset with
  forced password change + audit event]; MFA-ready architecture now,
  enforcement policy later [PENDING DECISION].

## S2. AI / automation authority

AI agents hold ONLY scoped READ-ONLY API credentials for retrieval. Write-capable
tokens are held by the application layer under human approval workflows. No AI
path may post, approve, delete, or reconfigure (docs 04 §A4, 07 §C6).

## S3. Secrets management

- `.env` git-ignored in every repo used; templates contain placeholders only.
- No API keys/passwords/tokens/certificates in code, docs, logs, screenshots,
  prompts, or commits. Pre-commit secret scanning recommended for the future
  ERP repo [PROPOSAL].
- Rotation: rotate any credential suspected of exposure; document rotation
  procedure in the admin runbook.

## S4. Application & transport

- HTTPS everywhere; HSTS at proxy; TLS certs auto-renewed.
- Platform + dependencies patched on a schedule; vulnerability review before
  go-live and periodically thereafter [cadence PENDING DECISION].
- Attachments: access-controlled through the application only; direct file-path
  URL guessing must fail; uploads type/size-restricted; no executable upload
  serving.
- API endpoints: authentication required; rate-limit public-facing auth
  endpoints; CORS restricted to known origins.

## S5. Data & infrastructure

- DB reachable only inside the Docker network; never internet-exposed.
- Backups encrypted at rest where supported; off-site copy encrypted.
- Audit log: append-only, includes actor/timestamp/object/reason for every
  destructive or administrative action (doc D-009 policy).

## S6. Destructive operations policy

NO AUTONOMOUS DELETION by any agent or scheduled job. Archive → revoke
visibility → retention → controlled administrative deletion only if legally and
operationally appropriate. Every destructive action records: actor, timestamp,
reason, object, audit event.

## S7. Never-commit list (binding all terminals)

`.env`, API keys, passwords, tokens, private certificates, customer financial
data exports, production database dumps.
