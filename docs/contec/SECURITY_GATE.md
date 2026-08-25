# Contec ERP — Security Gate

Status: GATE DEFINED — evaluations NOT YET EXECUTED (nothing to evaluate pre-implementation)
Owner: Terminal 2 signs; evidence produced by Terminal 3 implementation
Last updated: 2026-08-25

## Purpose

Production is **NO-GO** while ANY critical control is missing or unevaluated.
There is no conditional pass. This gate is re-run: before go-live, after any
major change, and at a recurring review cadence [cadence PENDING DECISION].

## Gate checklist

| # | Control | Criticality | Required evidence | Status |
|---|---|---|---|---|
| 1 | Authentication enforced on all non-static routes | CRITICAL | negative test: unauthenticated request to each route class → denied | NOT EVALUATED |
| 2 | Server-side authorization (RBAC) incl. API layer | CRITICAL | permission suite (doc 12) green + raw-API negative tests | NOT EVALUATED |
| 3 | Least privilege: no daily-use Administrator accounts | CRITICAL | user list audit showing admin role only on designated admins | NOT EVALUATED |
| 4 | Creator ≠ approver enforced on financial approval | CRITICAL | workflow test attempting self-approval → rejected | NOT EVALUATED |
| 5 | Posted records immutable for all roles incl. admins* | CRITICAL | immutability test per role; *admin exceptions only via audited controlled flow | NOT EVALUATED |
| 6 | HTTPS everywhere + valid cert + HSTS | CRITICAL | scan/headers output | NOT EVALUATED |
| 7 | Secrets not in Git; templates placeholders-only | CRITICAL | secret scan clean on full history of ERP repo | NOT EVALUATED |
| 8 | DB not exposed publicly; internal network only | CRITICAL | port scan from outside + compose inspection | NOT EVALUATED |
| 9 | Attachments access-controlled (no direct URL access) | CRITICAL | unauthorized fetch attempt → denied | NOT EVALUATED |
| 10 | Audit log captures actor/timestamp/object/reason | CRITICAL | perform sample destructive+admin actions, inspect log entries | NOT EVALUATED |
| 11 | No AI/automation write credentials in production | CRITICAL | credential inventory check | NOT EVALUATED |
| 12 | Backup automated + restore drill passed | CRITICAL | doc 10 Y4 drill record | NOT EVALUATED |
| 13 | Session security (Secure/HttpOnly/SameSite/timeout) | HIGH | cookie inspection + idle timeout test | NOT EVALUATED |
| 14 | Upload restrictions (type/size), no executable serving | HIGH | upload test matrix | NOT EVALUATED |
| 15 | Rate limiting on auth endpoints | HIGH | brute-force probe behaves sanely | NOT EVALUATED |
| 16 | Patch level: platform + deps current at go-live | HIGH | version report vs release notes | NOT EVALUATED |
| 17 | Rollback procedure documented AND rehearsed once | HIGH | rollback drill note | NOT EVALUATED |

## Sign-off record

```
Gate result:        NO-GO (default until proven otherwise)
Evaluated by:       —
Date:               —
Critical failures:  ALL items pending evaluation
Re-evaluation due:  before any production exposure
```
