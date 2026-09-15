# Consumer Conviction Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the autonomous DemandFactory so every candidate product is evaluated for buyer relevance, proof, clarity, risk reduction, experience quality, creative quality, and measurable commercial fit before launch.

**Architecture:** Extend `MBM/DemandFactory` as the decision layer above the existing MBM pain-point, sales, revenue, Whop, Instagram/network, and artifact systems. Add a deterministic Conviction Engine that produces structured quality gates and next actions; add adapter contracts for Knowledge Graph, HubSpot, and Higgsfield without coupling the core engine to external APIs. Keep side effects proposal-only until an explicit armed execution path is added.

**Tech Stack:** Python 3, dataclasses, JSON, unittest; existing Node package scripts; GitHub branch/PR workflow.

**Spec:** `MBM/DemandFactory/DESIGN.md` plus the Consumer Conviction design agreed in chat.

## Global Constraints

- Evidence before invention.
- No fabricated demand, proof, contacts, testimonials, or performance claims.
- No manipulative dark patterns, fake scarcity, or deceptive guarantees.
- Product build should use the cheapest artifact capable of validating the demand hypothesis.
- Core engine stays deterministic and side-effect free.
- Live CRM writes, outreach, payments, and publishing require explicit execution gates.
- Reuse existing MBM systems instead of duplicating their capabilities.

---

### Task 1: Conviction data model and gates

**Files:**
- Modify: `MBM/DemandFactory/models.py`
- Modify: `MBM/DemandFactory/engine.py`
- Test: `MBM/DemandFactory/test_engine.py`

**Interfaces:**
- Add `ConvictionAssessment` with named dimensions for relevance, proof, outcome clarity, risk reduction, purchase friction, creative readiness, personalization, trust, and usage readiness.
- Add `ConvictionGateResult` with `status`, `failed_gates`, `passed_gates`, `score`, and `next_action`.
- Add `DemandFactory.assess_conviction(opportunity, conviction)` returning `ConvictionGateResult`.

- [ ] **Step 1: Write failing tests** for a low-conviction offer being blocked and a high-conviction offer passing.
- [ ] **Step 2: Run** `python -m unittest MBM.DemandFactory.test_engine -v` and verify the new tests fail.
- [ ] **Step 3: Implement** the dataclasses and deterministic threshold evaluation.
- [ ] **Step 4: Run** the test module and verify all tests pass.
- [ ] **Step 5: Commit** with `feat(factory): add consumer conviction gates`.

---

### Task 2: Product quality contract and evidence requirements

**Files:**
- Create: `MBM/DemandFactory/quality.py`
- Modify: `MBM/DemandFactory/test_engine.py`
- Modify: `MBM/DemandFactory/README.md`

**Interfaces:**
- Add `ProductQualityContract` with required deliverables: outcome statement, proof inventory, buyer preview, usage path, objection map, refund/limitation disclosure, and QA checklist.
- Add `validate_quality_contract(contract)` returning structured failures.
- Add `minimum_proof_level` enforcement so unsupported claims cannot mark a product launch-ready.

- [ ] **Step 1: Write failing tests** for missing proof, missing preview, and successful complete contract.
- [ ] **Step 2: Run** `python -m unittest MBM.DemandFactory.test_engine -v` and confirm failure.
- [ ] **Step 3: Implement** `quality.py` with pure validation functions.
- [ ] **Step 4: Run** the tests and confirm pass.
- [ ] **Step 5: Update** README with the quality contract and commit `feat(factory): enforce product quality contract`.

---

### Task 3: Knowledge Graph adapter contract

**Files:**
- Create: `MBM/DemandFactory/adapters/knowledge_graph.py`
- Create: `MBM/DemandFactory/adapters/__init__.py`
- Create: `MBM/DemandFactory/test_adapters.py`

**Interfaces:**
- Add `KnowledgeGraphAdapter` protocol with `record_relationships(opportunity_id, relationships)` and `lookup_context(opportunity_id)`.
- Add `NullKnowledgeGraphAdapter` as safe default.
- Relationships must connect demand, buyer, pain, offer, proof, objection, creative, channel, and outcome concepts without storing credentials or sensitive personal records.

- [ ] **Step 1: Write failing tests** for the null adapter and relationship payload validation.
- [ ] **Step 2: Run** `python -m unittest MBM.DemandFactory.test_adapters -v` and verify failure.
- [ ] **Step 3: Implement** the protocol and null adapter.
- [ ] **Step 4: Run** adapter tests and verify pass.
- [ ] **Step 5: Commit** `feat(factory): add knowledge graph adapter contract`.

---

### Task 4: HubSpot commercial-memory adapter contract

**Files:**
- Create: `MBM/DemandFactory/adapters/hubspot.py`
- Modify: `MBM/DemandFactory/test_adapters.py`
- Modify: `MBM/DemandFactory/DESIGN.md`

**Interfaces:**
- Add `HubSpotCommercialAdapter` with proposal-only methods `build_opportunity_payload`, `build_deal_payload`, and `record_learning_event` that return data but never call HubSpot.
- Payloads should support contacts/companies/deals without requiring writes.
- Store attribution dimensions: opportunity, offer, product, distributor, channel, campaign, outcome.

- [ ] **Step 1: Write failing serialization/validation tests.
- [ ] **Step 2: Run adapter tests and verify failure.
- [ ] **Step 3: Implement the proposal-only adapter.
- [ ] **Step 4: Run adapter tests and verify pass.
- [ ] **Step 5: Document the adapter boundary and commit `feat(factory): add hubspot commercial memory adapter`.

---

### Task 5: Higgsfield creative brief adapter

**Files:**
- Create: `MBM/DemandFactory/adapters/higgsfield.py`
- Modify: `MBM/DemandFactory/test_adapters.py`
- Modify: `MBM/DemandFactory/README.md`

**Interfaces:**
- Add `HiggsfieldCreativeAdapter.build_asset_plan(product_context)` producing a structured plan for hero visual, product mockup, demo video, objection visual, social proof card, and UGC-style variants.
- The adapter must not submit generations; it creates prompts/requirements for later execution.
- Every asset must map to a specific product claim or buyer objection.

- [ ] **Step 1: Write failing tests** that require claim-to-asset mapping and reject orphan creative requests.
- [ ] **Step 2: Run** adapter tests and verify failure.
- [ ] **Step 3: Implement** the brief builder.
- [ ] **Step 4: Run** adapter tests and verify pass.
- [ ] **Step 5: Commit** `feat(factory): add creative asset planning adapter`.

---

### Task 6: End-to-end consumer conviction evaluation

**Files:**
- Modify: `MBM/DemandFactory/engine.py`
- Modify: `MBM/DemandFactory/__init__.py`
- Modify: `MBM/DemandFactory/__main__.py`
- Modify: `MBM/DemandFactory/sample_opportunity.json`
- Modify: `MBM/DemandFactory/test_engine.py`

**Interfaces:**
- Extend CLI JSON output with `conviction` and `next_best_action`.
- Add `DemandFactory.evaluate_full(...)` that evaluates evidence gates, commercial score, quality contract, conviction gates, and returns the single next action.
- Actions must include `validate_demand`, `repair_offer`, `build_product`, `complete_proof`, `complete_creative`, `launch_experiment`, `follow_up_sales`, `optimize_offer`, `scale_winner`, or `kill_opportunity`.

- [ ] **Step 1: Write failing end-to-end tests** covering blocked, repairable, launch-ready, and scale-ready opportunities.
- [ ] **Step 2: Run** the factory tests and verify failure.
- [ ] **Step 3: Implement** the orchestration method using existing deterministic components.
- [ ] **Step 4: Run** `python -m unittest MBM.DemandFactory.test_engine MBM.DemandFactory.test_adapters -v` and verify pass.
- [ ] **Step 5: Run** `python -m MBM.DemandFactory --file MBM/DemandFactory/sample_opportunity.json` and verify structured JSON output.
- [ ] **Step 6: Commit** `feat(factory): add full consumer conviction evaluation`.

---

### Task 7: Documentation and verification gate

**Files:**
- Modify: `MBM/DemandFactory/DESIGN.md`
- Modify: `MBM/DemandFactory/README.md`
- Modify: `package.json` only if the factory command is missing or incorrect

**Interfaces:**
- Document the final state machine, quality gates, adapter boundaries, and next-best-action rules.
- Preserve proposal-only defaults.

- [ ] **Step 1: Run** all factory unit tests.
- [ ] **Step 2: Run** the CLI sample.
- [ ] **Step 3: Run** the repository's applicable lint/type/build commands when available; do not introduce unrelated dependency changes.
- [ ] **Step 4: Compare branch against `master` and review only intended files.
- [ ] **Step 5: Commit** `docs(factory): document consumer conviction architecture`.
