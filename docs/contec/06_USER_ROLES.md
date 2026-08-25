# 06 — User Roles & Capability Architecture

Status: PROPOSED — capability areas fixed; detailed matrix PENDING DECISION (later milestone)
Owner: Terminal 1 (content) / Terminal 2 (verification)
Last updated: 2026-08-25

## R1. Scope note

~10 users at go-live. The exact per-document permission matrix is deliberately
NOT finalized here. This document fixes the capability architecture that the
platform must support; the matrix lands in a later milestone with named users.

## R2. Capability domains

| Domain | Example capabilities |
|---|---|
| Financial posting | create/submit invoices, bills, payments, JEs |
| Financial approval | approve/submit-to-ledger others' drafts |
| Financial administration | CoA, fiscal years, opening balances, tax setup |
| Project data | create projects/cost centers, budgets |
| Site operations | material issues, site store counts, site expenses draft |
| Procurement | POs, supplier onboarding (draft), receipt of materials |
| Stores | receipts, issues, transfers, stock takes |
| Reporting | read dashboards/reports within allowed scope |
| User administration | create users, assign roles (segregated) |
| Audit | read-only full audit trail |

## R3. Role archetypes → default domain mapping (PROPOSAL)

| Archetype | Domains (typical) |
|---|---|
| Owner/Director | all read + approval + user admin delegation |
| General Manager | broad read + approvals |
| Chief Accountant | full financial posting+approval+administration |
| Accountant | financial posting (no administration) |
| Project Manager | project data + project-scoped reporting + draft costs |
| Site Engineer | site operations drafts (no posting) |
| Procurement Officer | procurement domain |
| Storekeeper | stores domain |

Least privilege defaults: a role grants NOTHING until explicitly added.
No normal user receives Administrator/System-manager privileges — platform
admin role is restricted to designated administrators and documented.

## R4. Hard requirements on any platform

1. Permission check server-side for every action (UI hiding is not security).
2. Permissions can distinguish document STATES (draft vs submitted vs posted;
   e.g., accountant may post, site engineer may only draft).
3. Segregation of duties: creator ≠ approver on same document (configurable,
   ON by default for payments).
4. Audit identity: every create/edit/post/view-sensitive/delete-archive event
   records the authenticated actor. Shared accounts prohibited.
5. Administrator actions are audited like everything else.

## R5. Authentication foundation (now) vs hierarchy (later)

NOW (architecture): login required from first deployment; secure session
handling; strong password hashing by the platform; login/logout events
audited; account recovery strategy defined; MFA-ready (enable without schema
break later).

LATER (explicitly deferred): named 10-user matrix, MFA enforcement policy.

No real passwords in Git. Non-production environments use placeholder users
with obviously-fake credentials only.

## Open items

1. Named-user matrix. [PENDING DECISION — later milestone]
2. Platform capability proof for R4.1–R4.4 per candidate. [bake-off scenarios 22–23]
