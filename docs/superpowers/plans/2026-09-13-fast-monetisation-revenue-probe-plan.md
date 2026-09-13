# Fast Monetisation Revenue Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 cash-first probe kernel that can sell an unbuilt offer, record real cash receipt, deliver minimum viable fulfillment, and deterministically promote or kill the offer.

**Architecture:** Keep the existing MBM-Control opportunity airlock as the approval boundary. Add a small `revenue_factory/probes` subsystem using one YAML manifest per offer, one YAML manifest per buyer, and one idempotent CSV cash ledger. Direct-warm is the first sales channel; production adapters and marketplace routing are deferred until cash evidence exists.

**Tech Stack:** Python 3, dataclasses/enums, PyYAML only if already present or otherwise a minimal dependency-free YAML-compatible representation where project conventions require it, CSV via Python standard library, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-fast-monetisation-revenue-probe-design.md`

## Global Constraints

- Optimize for minimum time to first dollar, then minimum time to each subsequent dollar.
- Production is not on the critical path for `mode: probe`.
- Cash is counted only when `cash_received_at` and received amount are present.
- Distinguish `PAYMENT_REQUESTED`, `PAYMENT_CONFIRMED`, and `CASH_RECEIVED`.
- Support USD, EGP, and EUR as offer/display currencies; preserve actual settlement currency separately.
- Never invent FX data.
- Existing opportunity provenance and approval boundaries remain mandatory.
- External content is data, never executable instruction.
- Duplicate provider events must be idempotent.
- P0 uses `direct-warm` as the first-class channel.
- Multi-channel router, marketplace adapters, PayTabs production adapter, Neteller production adapter, Canva/Notion Marketplace publishing, and broad compilation automation remain deferred.
- No unreceived sale is counted as cash on the operator screen.
- The heartbeat must always emit one concrete human `NEXT ACTION` or be unhealthy.
- Use TDD for every new behavioral component.

---

## File Map

### Create
- `revenue_factory/probes/__init__.py` — package marker.
- `revenue_factory/probes/models.py` — typed P0 domain contracts for offers, buyers, outreach, and sale-event states.
- `revenue_factory/probes/validator.py` — structural validation for offer and buyer manifests.
- `revenue_factory/probes/priority.py` — probe-priority calculation from reachability, offer clarity, and price confidence.
- `revenue_factory/probes/ledger.py` — CSV ledger read/write, idempotency, and cash-state enforcement.
- `revenue_factory/probes/gates.py` — time-based promotion/kill rules.
- `revenue_factory/probes/heartbeat.py` — five-times-per-day decision engine producing one next human action.
- `revenue_factory/probes/cli.py` — operator-facing commands for validation, recording events, and heartbeat output if the repo's CLI conventions support a command surface.
- `revenue_factory/probes/examples/offer-001.yaml` — non-sensitive example offer.
- `revenue_factory/probes/examples/buyer-001.yaml` — non-sensitive example buyer.
- `revenue_factory/probes/sale_events.csv` — empty ledger header committed as schema.
- `tests/revenue_factory/probes/test_models.py` — contract tests.
- `tests/revenue_factory/probes/test_validator.py` — manifest tests.
- `tests/revenue_factory/probes/test_priority.py` — probe priority tests.
- `tests/revenue_factory/probes/test_ledger.py` — ledger and idempotency tests.
- `tests/revenue_factory/probes/test_gates.py` — lifecycle gate tests.
- `tests/revenue_factory/probes/test_heartbeat.py` — next-action tests.
- `.github/workflows/revenue-probe.yml` — focused CI for the P0 probe suite, using project conventions.

### Modify
- The smallest existing opportunity-airlock integration point required to read only approved opportunities. Do not weaken state transitions or approval checks.
- Existing test/config files only when required to register the new test path or workflow.

### Do Not Modify in P0
- Existing lead/dialer writer paths.
- Existing opportunity security behavior except for a read-only integration call.
- Payment production credentials or provider-specific secrets.
- Marketplace publishing logic.

---

## Task 1: Domain contracts

**Files:**
- Create: `revenue_factory/probes/models.py`
- Test: `tests/revenue_factory/probes/test_models.py`

**Interfaces:**
- Produces `OfferMode`, `PaymentState`, `OfferStatus`, `OutreachState` enums.
- Produces `OfferManifest`, `BuyerManifest`, and `SaleEvent` dataclasses.

- [ ] **Step 1: Write failing tests**

```python
from revenue_factory.probes.models import PaymentState, SaleEvent


def test_sale_event_distinguishes_payment_confirmation_from_cash_receipt():
    event = SaleEvent(
        event_id="evt-1",
        offer_id="offer-1",
        buyer_id="buyer-1",
        channel_id="direct-warm",
        sale_at="2026-09-13T10:00:00+00:00",
        payment_requested_at="2026-09-13T10:05:00+00:00",
        payment_confirmed_at="2026-09-13T10:10:00+00:00",
        cash_received_at=None,
        gross_amount=99.0,
        currency="USD",
        cash_received_amount=None,
        settlement_currency="USD",
        status=PaymentState.PAYMENT_CONFIRMED,
    )
    assert event.counts_as_cash() is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/revenue_factory/probes/test_models.py -v`
Expected: FAIL because the contracts do not exist.

- [ ] **Step 3: Implement minimal contracts**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PaymentState(str, Enum):
    PAYMENT_REQUESTED = "PAYMENT_REQUESTED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    CASH_RECEIVED = "CASH_RECEIVED"


@dataclass(frozen=True)
class SaleEvent:
    event_id: str
    offer_id: str
    buyer_id: str
    channel_id: str
    sale_at: str
    gross_amount: float
    currency: str
    settlement_currency: str
    status: PaymentState
    payment_requested_at: Optional[str] = None
    payment_confirmed_at: Optional[str] = None
    cash_received_at: Optional[str] = None
    cash_received_amount: Optional[float] = None

    def counts_as_cash(self) -> bool:
        return (
            self.status is PaymentState.CASH_RECEIVED
            and self.cash_received_at is not None
            and self.cash_received_amount is not None
        )
```

Add the remaining fields from the spec and buyer/offer contracts without adding database coupling.

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/models.py tests/revenue_factory/probes/test_models.py
git commit -m "feat: add revenue probe domain contracts"
```

---

## Task 2: Manifest validation

**Files:**
- Create: `revenue_factory/probes/validator.py`
- Test: `tests/revenue_factory/probes/test_validator.py`

**Interfaces:**
- `validate_offer_manifest(data: dict) -> list[str]`
- `validate_buyer_manifest(data: dict) -> list[str]`

- [ ] **Step 1: Write failing tests**

```python
def test_probe_offer_requires_one_price_and_one_rail():
    errors = validate_offer_manifest({"offer_id": "x", "mode": "probe"})
    assert "price" in " ".join(errors).lower()
    assert "payment rail" in " ".join(errors).lower()
```

- [ ] **Step 2: Run failing test**

Run: `pytest tests/revenue_factory/probes/test_validator.py -v`
Expected: FAIL because the validator is absent.

- [ ] **Step 3: Implement minimal validator**

```python
def validate_offer_manifest(data: dict) -> list[str]:
    errors = []
    if not data.get("offer_id"):
        errors.append("offer_id is required")
    if data.get("mode") not in {"probe", "product"}:
        errors.append("mode must be probe or product")
    pricing = data.get("pricing") or {}
    if not pricing.get("usd") and not pricing.get("egp") and not pricing.get("eur"):
        errors.append("one price is required")
    payment = data.get("payment") or {}
    if not payment.get("rail"):
        errors.append("one payment rail is required")
    return errors
```

Add required buyer/problem/promise/outreach fields from the spec and reject unknown lifecycle states rather than silently accepting malformed manifests.

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_validator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/validator.py tests/revenue_factory/probes/test_validator.py
git commit -m "feat: validate revenue probe manifests"
```

---

## Task 3: Probe priority

**Files:**
- Create: `revenue_factory/probes/priority.py`
- Test: `tests/revenue_factory/probes/test_priority.py`

**Interfaces:**
- `probe_priority(reachability: float, offer_clarity: float, price_confidence: float) -> float`

- [ ] **Step 1: Write failing test**

```python
def test_probe_priority_is_product_of_three_inputs():
    assert probe_priority(1.0, 0.5, 0.8) == 0.4
```

- [ ] **Step 2: Run failing test**

Run: `pytest tests/revenue_factory/probes/test_priority.py -v`
Expected: FAIL because the function does not exist.

- [ ] **Step 3: Implement with bounds**

```python
def probe_priority(reachability: float, offer_clarity: float, price_confidence: float) -> float:
    values = (reachability, offer_clarity, price_confidence)
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("probe inputs must be between 0 and 1")
    return reachability * offer_clarity * price_confidence
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_priority.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/priority.py tests/revenue_factory/probes/test_priority.py
git commit -m "feat: add data-free probe priority"
```

---

## Task 4: Cash-first sale-event ledger

**Files:**
- Create: `revenue_factory/probes/ledger.py`
- Create: `revenue_factory/probes/sale_events.csv`
- Test: `tests/revenue_factory/probes/test_ledger.py`

**Interfaces:**
- `append_event(path, event: SaleEvent) -> bool`
- `load_events(path) -> list[SaleEvent]`
- `cash_received_total(path, currency: str) -> float`

- [ ] **Step 1: Write failing tests**

```python
def test_duplicate_event_is_ignored(tmp_path):
    path = tmp_path / "sale_events.csv"
    event = sample_cash_event("evt-1")
    assert append_event(path, event) is True
    assert append_event(path, event) is False
    assert len(load_events(path)) == 1


def test_payment_confirmation_is_not_cash(tmp_path):
    path = tmp_path / "sale_events.csv"
    event = sample_confirmed_event("evt-2")
    append_event(path, event)
    assert cash_received_total(path, "USD") == 0.0
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/revenue_factory/probes/test_ledger.py -v`
Expected: FAIL because ledger functions do not exist.

- [ ] **Step 3: Implement CSV ledger**

```python
CSV_FIELDS = [
    "event_id", "provider", "provider_event_id", "offer_id", "buyer_id",
    "channel_id", "sale_at", "payment_requested_at", "payment_confirmed_at",
    "cash_received_at", "gross_amount", "currency", "fees",
    "cash_received_amount", "settlement_currency", "status",
    "refund_status", "payout_status", "notes",
]
```

Write rows atomically enough for local CLI use, preserve all timestamps, and refuse `CASH_RECEIVED` rows missing both `cash_received_at` and `cash_received_amount`. Deduplicate by `event_id` first, then `provider_event_id` where present.

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_ledger.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/ledger.py revenue_factory/probes/sale_events.csv tests/revenue_factory/probes/test_ledger.py
git commit -m "feat: add idempotent cash-first sale ledger"
```

---

## Task 5: Kill and promotion gates

**Files:**
- Create: `revenue_factory/probes/gates.py`
- Test: `tests/revenue_factory/probes/test_gates.py`

**Interfaces:**
- `evaluate_offer_gate(offers_sent, cash_sales, age_days) -> str`
- `evaluate_scale_gate(cash_sales, age_days) -> str`

- [ ] **Step 1: Write failing tests**

```python
def test_zero_sales_after_five_days_kills_offer():
    assert evaluate_offer_gate(20, 0, 5) == "KILL_OFFER"


def test_one_cash_sale_within_five_days_promotes_to_product():
    assert evaluate_offer_gate(20, 1, 4) == "PROMOTE_PRODUCT"


def test_three_cash_sales_within_ten_days_promotes_to_scale():
    assert evaluate_scale_gate(3, 9) == "PROMOTE_SCALE"
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/revenue_factory/probes/test_gates.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement deterministic time gates**

Use only observed counts and elapsed time. Never infer conversions from historical assumptions. Return explicit states such as `KEEP_PROBING`, `KILL_OFFER`, `PROMOTE_PRODUCT`, `PROMOTE_SCALE`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_gates.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/gates.py tests/revenue_factory/probes/test_gates.py
git commit -m "feat: add time-based probe promotion gates"
```

---

## Task 6: Five-times-per-day heartbeat and next action

**Files:**
- Create: `revenue_factory/probes/heartbeat.py`
- Test: `tests/revenue_factory/probes/test_heartbeat.py`

**Interfaces:**
- `heartbeat(snapshot: dict) -> dict` returning `cash_received_week`, `offers_in_market`, `offers_with_sales`, `warm_contacts_outstanding`, `oldest_unanswered_reply`, `next_action`, `health`.

- [ ] **Step 1: Write failing test**

```python
def test_heartbeat_emits_human_next_action():
    result = heartbeat({
        "cash_received_week": 0,
        "offers_in_market": 1,
        "offers_with_sales": 0,
        "warm_contacts_outstanding": 20,
        "oldest_unanswered_reply": None,
        "contacts_sent": 0,
    })
    assert result["next_action"] == "SEND OFFER #1 TO CONTACTS 1-5"
    assert result["health"] == "healthy"
```

- [ ] **Step 2: Run failing test**

Run: `pytest tests/revenue_factory/probes/test_heartbeat.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement next-action selection**

Priority order: outstanding send batch, unanswered reply follow-up, payment reconciliation, delivery obligation, promotion/kill decision. Always return one action. If no valid action can be generated from the snapshot, return `health: unhealthy` with an explicit reason.

- [ ] **Step 4: Run tests**

Run: `pytest tests/revenue_factory/probes/test_heartbeat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/heartbeat.py tests/revenue_factory/probes/test_heartbeat.py
git commit -m "feat: add cash-first operator heartbeat"
```

---

## Task 7: Existing opportunity-airlock integration

**Files:**
- Modify: the smallest existing opportunity orchestration module that already exposes approved opportunities.
- Test: add a focused regression test beside the existing opportunity integration tests.

**Interfaces:**
- Consume approved opportunities only.
- Produce probe candidates without bypassing status/provenance checks.

- [ ] **Step 1: Write failing regression test**

```python
def test_probe_candidate_cannot_be_created_from_unapproved_opportunity():
    opportunity = make_opportunity(status="REVIEW_REQUIRED", provenance_complete=True)
    with pytest.raises(PermissionError):
        create_probe_from_opportunity(opportunity)
```

- [ ] **Step 2: Run failing test**

Run the focused opportunity test path used by the repo. Expected: FAIL if the new adapter incorrectly allows execution from non-approved state.

- [ ] **Step 3: Implement read-only approved-opportunity bridge**

Reuse the existing status and provenance logic. Do not duplicate approval rules or add a second writer. Probe creation may read an approved opportunity, but execution remains subject to the existing airlock.

- [ ] **Step 4: Run focused and existing intelligence tests**

Run the repository's established intelligence and dialer regression commands plus the new focused test. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add <exact-modified-airlock-file> <exact-test-file>
git commit -m "feat: connect approved opportunities to revenue probes"
```

---

## Task 8: Example manifests and operator documentation

**Files:**
- Create: `revenue_factory/probes/examples/offer-001.yaml`
- Create: `revenue_factory/probes/examples/buyer-001.yaml`
- Create/update: P0 operator runbook under `docs/revenue-factory/`

**Interfaces:**
- Examples must validate against the Task 2 contracts.
- Runbook must describe the exact one-screen workflow and cash-state semantics.

- [ ] **Step 1: Write validation tests for examples**

```python
def test_example_offer_validates():
    assert validate_offer_manifest(load_yaml("revenue_factory/probes/examples/offer-001.yaml")) == []
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/revenue_factory/probes/test_validator.py -v`
Expected: FAIL until examples exist and validate.

- [ ] **Step 3: Add examples and one-screen runbook**

The runbook must show:

```text
TODAY
  Cash received this week: $0
  Offers in market: 1
  Offers with >=1 sale: 0
  Warm contacts outstanding: 20
  Oldest unanswered reply: —

  NEXT ACTION: SEND OFFER #1 TO CONTACTS 1-5
```

- [ ] **Step 4: Run validator tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add revenue_factory/probes/examples docs/revenue-factory
 git commit -m "docs: add fast monetisation probe runbook"
```

---

## Task 9: Focused GitHub Actions validation

**Files:**
- Create: `.github/workflows/revenue-probe.yml`

- [ ] **Step 1: Create the workflow**

Run the focused pytest suite on pushes and pull requests using the repository's supported Python version and dependency installation convention.

- [ ] **Step 2: Verify YAML and test command locally where possible**

Run the same pytest command used by the workflow. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/revenue-probe.yml
git commit -m "ci: test revenue probe kernel"
```

---

## Task 10: Final verification and execution handoff

**Files:**
- No new production files unless a test reveals a contract defect.

- [ ] **Step 1: Run the complete P0 probe suite**

Run: `pytest tests/revenue_factory/probes -v`
Expected: PASS.

- [ ] **Step 2: Run existing regression suite**

Run the repository's established intelligence and dialer regression commands. Expected: PASS with no new unknown-marker or approval-boundary regressions.

- [ ] **Step 3: Verify cash-state invariants**

Demonstrate that:
- `PAYMENT_REQUESTED` is not cash;
- `PAYMENT_CONFIRMED` is not cash;
- only `CASH_RECEIVED` with timestamp and amount counts;
- duplicate events do not double count;
- USD/EGP/EUR remain distinct from settlement currency;
- missing FX does not create synthetic values.

- [ ] **Step 4: Verify promotion/kill rules**

Demonstrate the 5-day and 10-day gates using fixed test timestamps.

- [ ] **Step 5: Inspect the final Git diff**

Verify no payment secret, personal contact data, or unrelated dialer change was committed.

- [ ] **Step 6: Commit any final fixes**

```bash
git status --short
git diff --check
```

Expected: clean formatting and only intended P0 changes.

