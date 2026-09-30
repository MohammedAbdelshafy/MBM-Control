# P4 Lead Cleaner: Managed SaaS Implementation & Commercialization Specification

**Status:** SPECIFICATION / NOT IMPLEMENTED BY THIS DOCUMENT  
**Product:** P4 Lead Cleaner & Qualification  
**Owner:** MBM / Jarvis  
**Primary control plane:** `MohammedAbdelshafy/jarvis-mbm`  
**Existing execution code:** `MohammedAbdelshafy/MBM-Control`  
**Decision rule:** paid validation before new engineering  
**External actions:** policy-controlled; no autonomous outreach, publishing, billing changes, or destructive actions

## 1. Executive decision

Productize the existing deterministic Lead Cleaner as a managed SaaS only by wrapping its current verification and qualification engines. Do not rewrite the cleaner, create a competing lead database, or create a second mission/control plane.

The fastest path to revenue remains the already documented done-for-you (DFY) pilot: accept an authorized customer-supplied CSV/JSON, run the existing local pipeline, manually QA the output, and deliver the cleaned CSV plus report. Build the hosted SaaS wrapper only after at least one paid DFY pilot or other concrete customer evidence demonstrates demand for self-service/repeat processing. A working local runner is not evidence that the SaaS is deployed.

## 2. Repository inspection: observed baseline

### Verified from repository files and issue #54

- `MBM-Control/productized-service/p4-lead-cleaner/clean_leads.py` exists and calls the canonical `MBM.LeadEngine.dialer_verification_gate.check_lead` gate.
- The cleaner supports CSV and JSON input, normalizes selected phone/name fields, classifies records, detects duplicate phone numbers, consults suppression/quarantine artifacts, and emits three artifacts: `cleaned.csv`, `summary.json`, and `report.md`.
- `MBM-Control/MBM/LeadEngine/qualification_runner.py` exists and describes itself as read-only; it evaluates records through the same canonical gate and does not write to the live dialer database or queue.
- `MBM-Control/package.json` has the existing `leads:qualify` command.
- `productized-service/p4-lead-cleaner/landing.html` exists. It currently describes a $499 cleanup offer for up to 10,000 records, a free 1,000-record sample, and a monthly plan from $49.
- GitHub issue #54 records successful synthetic/demo checks and prior CI checks, but also records that the P4 landing route was not present on the checked Vercel app and deployment was blocked by missing Vercel authentication at that time. Recheck live status before making any current deployment claim.
- `jarvis-mbm` describes itself as the business control plane, with mission lifecycle, revenue reporting, customer pipeline, and the rule to wrap existing scripts behind stable interfaces before replacing internals.
- `jarvis-mbm/SYSTEMS/AGENCY_OS.md` already defines a Data Quality Engine and the canonical opportunity lifecycle. Reuse it.
- `jarvis-mbm` issue #88 requires productization to be evidence-backed, prohibits duplicate control planes, requires human approval for external actions, and distinguishes VERIFIED / INFERRED / EXAMPLE / UNKNOWN.

### Unknown / must verify before SaaS launch

- Current production deployment status, current CI status, and current working-tree state.
- Current end-to-end behavior of the cleaner against current schemas and suppression files.
- Whether each advertised verification source is actually configured and used for a given customer run.
- Whether any live DNC source is available, current, licensed, and actually checked. A local suppression index is not proof of a comprehensive DNC check.
- Current storage, authentication, tenant isolation, payment, webhook, deletion, backup, and job-queue capabilities suitable for this product.
- Actual per-job infrastructure costs, support burden, customer willingness to pay, and production service-level performance.
- Whether existing price/turnaround claims remain feasible at current capacity.

## 3. Product and customer

### Initial ideal customer profile

US small and midsize businesses that already possess lawful, customer-authorized B2B or consumer lead lists and spend time cleaning them before CRM import or sales operations. Initial discovery focus: real-estate investors/wholesalers and other small sales teams with recurring CSV workflows.

### Job to be done

“Before my team imports or works this list, show me duplicates, missing/invalid fields, records blocked by configured suppression rules, records with verification evidence, and records that need manual review.”

### Deliverables

- Normalized output CSV preserving original columns and adding deterministic result fields.
- Machine-readable summary JSON.
- Human-readable quality report with counts, reason-code breakdown, processing timestamp, ruleset/version, and explicit limitations.
- Job receipt with job ID, row counts, status, and download expiry.
- Optional audit manifest recording input hash, output hashes, ruleset version, and timestamps without copying raw PII into logs.

### Product boundaries

- Customer supplies the file and confirms lawful authority to process it.
- Do not promise that a phone will answer, that a person owns a number, that a record will convert, or that a record is legally callable.
- “CALLABLE” is a product status from the configured gate, not legal advice or a guarantee that a call is lawful.
- Never describe an internal suppression file as a comprehensive national DNC check unless the source, freshness, coverage, and legal basis have been verified.
- No skip tracing, live carrier lookups, or enrichment unless a specific provider, entitlement, data provenance, cost, and customer disclosure are verified.
- No automatic calling, emailing, CRM writes, list resale, or external publication in the initial product.

## 4. Delivery roadmap

### Phase 0: Paid validation (do this first)

1. Use the existing DFY offer and existing local runner; do not wait for a new SaaS UI.
2. Offer a bounded sample using customer-authorized data, with the record cap and sensitive-field handling explained before transfer.
3. For a free sample, agree a safe subset (default: up to 1,000 rows) and manually review the result.
4. For the paid pilot, offer the documented $499 / up-to-10,000-row scope as a **price hypothesis to validate**, with turnaround confirmed after capacity and file checks.
5. Obtain explicit permission for processing and secure transfer. Never ask customers to send files containing unnecessary sensitive data.
6. Track only evidenced funnel events: prospect identified, message approved, message sent, reply received, sample accepted, offer made, payment confirmed, delivery accepted, repeat request.
7. Continue only if real customer feedback supports the next investment.

**Gate to Phase 1:** at least one confirmed paid pilot delivered successfully, or documented repeated customer requests for self-service/recurring processing. A prospect list or demo alone does not satisfy this gate.

### Phase 1: Minimum managed SaaS wrapper

Reuse existing scripts behind a stable service interface. Do not rewrite the verification gate.

1. Authenticated customer workspace and tenant identity.
2. File intake for CSV/JSON with strict size, encoding, schema, row-count, and file-type checks.
3. Job creation with idempotency key, tenant-scoped job ID, queued/running/completed/failed states, bounded retries, and a cancellation path.
4. Isolated temporary input/output storage per tenant, encryption in transit and at rest, short-lived signed downloads, and configurable deletion/retention.
5. Worker adapter that invokes the existing deterministic pipeline in a restricted process/container with no unnecessary network access.
6. Tenant-safe job history and status page; no cross-tenant query path.
7. Download bundle containing the three existing artifacts plus job receipt/audit manifest.
8. Usage metering based on successfully processed rows, not retries or duplicate webhook deliveries.
9. Payment provider adapter only after choosing and testing an actually available processor for the business. Do not assume Stripe or any unconfigured provider.
10. Support/incident path, job-failure visibility, cost caps, rate limits, and a kill switch.
11. Reuse the current product registry and Jarvis mission/event conventions. Do not add a separate orchestration database or a parallel lead store.

### Phase 2: Recurring workflow

Only after usage evidence: recurring uploads, CRM integrations, API access, scheduled jobs, team seats, and custom rules. Each integration is separately permissioned, tested, costed, and customer-approved.

## 5. Target architecture

```text
Customer
  |
  v
Existing approved MBM/Jarvis product entry point
  |
  v
Tenant-authenticated intake API
  |-- authentication / tenant authorization
  |-- schema + file safety checks
  |-- quota / billing entitlement check
  |-- idempotency
  v
Job record + queue (reuse an existing approved service if suitable)
  |
  v
Isolated worker
  |-- existing qualification_runner / clean_leads.py adapter
  |-- canonical dialer_verification_gate
  |-- configured suppression + provenance inputs
  v
QA gates + artifact manifest
  |
  v
Tenant-scoped encrypted output storage
  |
  v
Short-lived download + audit event + usage record
```

The agent/LLM layer is optional and not required for the core cleaning path. Keep deterministic classification as the source of truth. If an LLM is later used to map unusual column headers, it may suggest a mapping but must not override suppression, verification, or classification results.

## 6. Policy-controlled automation

Enforce these controls in the backend/tool boundary, not only in prompts.

- **Autonomous, low risk:** parse file metadata, validate schema, run deterministic cleaning in the customer's authorized job, calculate counts, produce reports, retry transient internal failures within a fixed budget.
- **Require customer confirmation:** upload submission, processing of a newly selected file, enabling paid recurring jobs, connecting a CRM, expanding row limits, changing retention, enabling enrichment, or changing suppression rules.
- **Require authorized human approval:** external messages, CRM write-back, sharing/export to a third party, refunds/credits outside policy, account privilege changes, production deployment, destructive bulk deletion, or changes to compliance gates.
- **Never permitted for the agent:** bypass suppression, invent verification, silently upgrade a plan, reuse one tenant's data for another tenant, expose credentials, disable audit logging, or change policy/approval rules.
- Every action must include actor/tenant, job ID, action, normalized parameters or their safe hash, policy version, allow/deny decision, approval ID when applicable, timestamp, and outcome.
- Approval must bind to the exact action and expire. Parameter changes require a new approval.
- Fail closed if tenant identity, authorization, suppression evaluation, audit persistence, or required approval cannot be verified.
- Treat uploaded files, CSV cells, external content, and tool results as untrusted data; never interpret their contents as agent instructions.

Security design aligns with the OWASP Agent Security Cheat Sheet's guidance on least privilege, backend enforcement, human approval, cost limits, and auditable tool execution: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

## 7. Data handling and privacy

- Collect only fields required for the customer's requested processing.
- Display allowed file formats, row/size limits, purpose, retention, deletion path, and support contact before upload.
- Use tenant-scoped access checks on every job and artifact read/write.
- Do not write raw lead rows, full phone numbers, email addresses, names, credentials, or uploaded file contents to ordinary logs.
- Encrypt transport and stored files; keep secrets in the configured secret manager, never in Git or client-side code.
- Set a short default retention window for raw uploads and outputs; proposed starting policy: delete raw inputs within 24 hours after successful processing and delete artifacts after 7 days unless the customer explicitly chooses a different disclosed retention plan. Confirm operational/legal requirements before implementing.
- Provide a tenant-scoped deletion request and record the result without retaining deleted PII.
- Keep synthetic test fixtures synthetic. Never commit customer data.
- Define processor/subprocessor terms and cross-border processing disclosures before production onboarding.

## 8. Acceptance criteria

### Functional

1. CSV and JSON supported; malformed, empty, oversized, or unsupported files rejected with actionable errors.
2. Output includes original fields plus documented P4 fields and preserves row accounting.
3. The canonical verification gate remains the only source of truth for qualification decisions.
4. Duplicate and suppression outcomes are deterministic and include reason codes.
5. Identical input + same ruleset + same reference suppression data produces identical classifications and counts.
6. Every job produces `cleaned.csv`, `summary.json`, `report.md`, and a job receipt/manifest.
7. Partial failure never produces a false “completed” state.
8. Repeated request with the same idempotency key does not double-charge or duplicate the job.
9. Customer can retrieve only their own jobs and outputs.
10. Usage is metered exactly once per billable job according to published plan terms.

### Security / policy

11. Unauthenticated requests are denied.
12. Tenant A cannot read, overwrite, delete, or download Tenant B's artifacts, including via guessed IDs.
13. External send, CRM write, plan change, and destructive action are denied unless a valid, unexpired approval is bound to the exact parameters.
14. Audit sink unavailable -> no high-impact action proceeds.
15. Malicious CSV cell content cannot trigger command execution, prompt override, path traversal, or unintended tool calls.
16. File content and PII do not appear in normal application logs.
17. Per-tenant quotas, request size, worker timeout, retry count, and total cost are bounded.
18. Job cancellation and global kill switch stop pending work and prevent new dispatch.
19. Retention/deletion behavior is covered by tests and produces a verifiable outcome.
20. No production secrets or customer records in repository, screenshots, fixtures, or CI logs.

### Commercial

21. Customer sees a clear sample disclaimer, scope, limitations, price, turnaround, retention policy, and support channel before payment.
22. Sample data is labeled synthetic unless it is explicitly authorized customer data.
23. Payment state is reconciled from a verified provider event or operator-verified receipt, not from a browser redirect alone.
24. Delivery acceptance and any refund/credit are recorded as separate evidenced events.
25. Do not claim a deployment, customer, payment, savings, accuracy, or conversion rate without a source record.

## 9. Required test suite

- Unit tests for normalization, aliases, reason codes, dedupe, suppression, empty input, malformed JSON/CSV, unicode/BOM, and header edge cases.
- Golden-fixture regression tests for the existing demo inputs.
- Determinism test across repeated runs.
- Property tests for row-count conservation and no unexpected row loss.
- Tenant isolation tests across API, database queries, storage keys, and signed URLs.
- Authentication/authorization and expired-approval tests.
- Idempotency and duplicate webhook tests.
- Worker timeout, retry exhaustion, crash recovery, and cancellation tests.
- Prompt-injection tests using malicious values in CSV cells if any AI-assisted mapping is later added.
- PII redaction tests for application, worker, and error logs.
- Retention expiry and deletion tests.
- Billing tests for free samples, failed jobs, retries, partial failures, plan limits, and repeated events.
- End-to-end test: synthetic upload -> queued -> deterministic worker -> QA -> artifacts -> tenant-only download -> usage/audit record.
- Existing repository tests, lint, typecheck, build, and security checks must remain green. Record exact commands, commit SHA, and results in the implementation PR.

## 10. Commercialization offer

### Initial paid pilot (DFY before SaaS)

**Offer hypothesis:** $499 one-time for up to 10,000 customer-supplied records, with cleaned CSV, reason-coded results, summary JSON, and a human-reviewed report. The existing landing page proposes a 48-hour turnaround; only confirm that window after checking file suitability and current capacity.

**Sample:** up to 1,000 rows at no charge for qualified prospects, subject to safe transfer, authorized data, and a bounded manual review. Clearly state that the sample is not a guarantee of live phone reachability or legal call eligibility.

**Candidate recurring tiers (hypotheses, not verified market prices):**
- Starter: $49/month, up to 1,000 rows/month.
- Growth: $149/month, up to 10,000 rows/month.
- Scale: $499/month, up to 100,000 rows/month or an explicitly limited API allowance.

Do not publish SaaS tiers as available until tenant isolation, billing, job processing, support capacity, and cost-to-serve have been verified. Define overage, retention, turnaround, and failed-job treatment before checkout.

### Buyer-facing message

**Subject:** Want a quick quality check on your lead list?

Hi {{first_name}},

If your team is spending time sorting duplicates, incomplete records, and numbers that lack verification, we can run a bounded quality check on a list you’re authorized to process.

You’ll receive a cleaned CSV, reason codes for records that need attention, and a summary showing what changed. We don’t promise that a number will answer or that a record is legally callable.

Would a small sample using a file you’re authorized to share be useful?

Best,  
{{sender_name}}

This is draft copy only. A human must verify the recipient, approve the final message, and authorize sending. Never use any Contec mailbox.

### Demo script (5 minutes)

1. Show a clearly labeled synthetic CSV with malformed phone formatting, missing fields, duplicate rows, a suppressed fixture, and an unverified record.
2. Show the exact command used by the existing runner; do not simulate a successful production API.
3. Run the deterministic cleaner and show job completion.
4. Open `cleaned.csv`; filter by each status and inspect reason codes.
5. Open `summary.json` and `report.md`; reconcile total rows and category counts.
6. Explain that “CALLABLE” is a rules-based product status, not a guarantee or legal determination.
7. Show the proposed tenant/job workflow as a roadmap mockup only if clearly labeled “not deployed.”
8. Offer the free bounded sample and then the paid DFY pilot. Ask for a real customer dataset only through the agreed secure intake method.

## 11. Unit economics: initial planning estimate

These are planning assumptions, not measured MBM costs. Validate with actual hosting/provider quotes and a measured pilot.

| Cost category | Early monthly planning range |
|---|---:|
| App/API and worker hosting | $10–$60 |
| Database / queue / storage / backups | $0–$50 |
| Transactional email / alerts | $0–$20 |
| AI inference | $0 for deterministic core; optional later |
| Payment processing | Provider-dependent; model separately |
| Human QA/support | 15–60 minutes per small job as an initial assumption |
| Customer acquisition | Excluded; measure actual founder hours and paid channel spend |

A minimal early hosted footprint might be approximately $10–$130/month before payment fees, enrichment, acquisition, and human labor. It can be higher depending on deployment choice, file volume, storage, compliance needs, and provider pricing. Do not set gross-margin claims from this estimate.

Track per job: rows received, rows processed, worker duration, retries, storage duration, provider cost, human minutes, support events, refund/credit, and revenue actually received.

## 12. First-pilot scorecard

A pilot is ready to deliver when:
- The customer has confirmed lawful authority to provide the file.
- The scope, row cap, turnaround, price, and limitations are acknowledged.
- Payment is verified for paid work.
- Input file passes validation and safe transfer checks.
- Output artifacts are generated and independently QA-checked.
- Suppression and provenance semantics are accurately represented.
- Delivery is made through the agreed channel.
- Customer acceptance, issues, and next request are recorded.

**Success evidence:** a real authorized dataset processed, verified payment if paid, accepted delivery, documented feedback, and measured delivery cost/time. A demo or outreach draft is not a sale.

## 13. Immediate next actions

1. **Commercial first:** use existing offer and approved outreach workflow to validate the free sample and paid DFY pilot; do not wait for SaaS engineering.
2. Verify current deployment and CI status; do not infer it from the historical issue.
3. Re-run the current cleaner and qualification regression tests on synthetic fixtures.
4. Inspect the real suppression/provenance implementation and reconcile every landing-page claim against code.
5. Measure a representative synthetic job for runtime, memory, artifact correctness, and manual QA time.
6. Only after the Phase 0 gate, select the smallest existing hosting/auth/storage/queue components that meet tenant-isolation requirements.
7. Implement in a scoped branch/PR with acceptance tests and human review; no direct production deployment without explicit authorization.
8. Update the existing product registry and Jarvis mission/report with evidence links and VERIFIED / INFERRED / EXAMPLE / UNKNOWN status.

## 14. Founder decision requested

**Approve the sequence, not an open-ended build:** sell and deliver the first DFY pilot with the existing runner, measure it, and only then authorize the minimum SaaS wrapper if customer evidence supports it.

No deployment, payment, customer, or revenue is claimed by this specification.
