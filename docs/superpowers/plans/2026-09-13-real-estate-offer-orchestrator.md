# Real-Estate Offer Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect public-web evidence and legitimate investor/buyer enrichment to the existing MBM canonical deal model, producing a verified offer packet for the user to send by email/WhatsApp and call manually.

**Architecture:** Add a small, pure-Python orchestration layer under `MBM/LeadEngine/real_estate/`. Scrapling remains the acquisition substrate and must preserve provenance; Vibe Prospecting/Clay remain external enrichment sources. The new layer normalizes evidence, applies deterministic underwriting gates, creates a human-review offer packet, and emits a dialer-ready payload without sending contracts or messages automatically.

**Tech Stack:** Python 3, dataclasses, existing `CanonicalDeal`, pytest, existing MBM lead/property intelligence modules. No new runtime service or database dependency.

**Spec:** `docs/SCRAPLING_STANDARD.md` plus the approved in-chat real-estate deal-engine design.

## Global Constraints

- Scraping is collection only; domain systems retain authority over scoring, CRM writes, outreach, and decisions.
- Preserve source URL/provenance for every externally sourced assertion.
- Explicitly represent blocked, empty, and malformed source outcomes.
- Do not fabricate business, property, owner, phone, or email data.
- No autonomous contract execution or closing.
- No automatic outbound transmission; the user receives copy-ready email/WhatsApp content and a call handoff.
- Reuse `CanonicalDeal` and existing property-intelligence calculations rather than creating a competing deal schema.

---

### Task 1: Normalized evidence and offer-packet contracts

**Files:**
- Create: `MBM/LeadEngine/real_estate/__init__.py`
- Create: `MBM/LeadEngine/real_estate/contracts.py`
- Test: `MBM/LeadEngine/real_estate/tests/test_contracts.py`

**Interfaces:**
- `PropertyEvidence(address: str, city: str, state: str, source_url: str, source_name: str, status: str, fields: dict[str, object])`
- `BuyerEvidence(name: str, source_url: str, source_name: str, status: str, buy_box: dict[str, object], contact: dict[str, object])`
- `OfferPacket` with immutable-looking public fields for property, economics, seller contact, buyer match, email copy, WhatsApp copy, and manual-call payload.
- `validate_evidence_status(status: str) -> str` accepting only `ok`, `blocked`, `empty`, `malformed`.

- [ ] **Step 1: Write the failing test**

```python
def test_offer_packet_rejects_missing_property_provenance():
    packet_data = {
        "property": {"address": "123 Main St"},
        "source_url": "",
    }
    with pytest.raises(ValueError, match="source_url"):
        OfferPacket.from_mapping(packet_data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_contracts.py::test_offer_packet_rejects_missing_property_provenance -v`
Expected: FAIL because `OfferPacket` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement the dataclasses and provenance/status validation. `OfferPacket.from_mapping()` must reject empty source URLs for externally sourced property/buyer evidence and preserve explicit blocked/empty/malformed statuses.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_contracts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate docs/superpowers/plans/2026-09-13-real-estate-offer-orchestrator.md
git commit -m "feat: add real-estate evidence and offer contracts"
```

---

### Task 2: Deterministic underwriting and human gate

**Files:**
- Create: `MBM/LeadEngine/real_estate/underwriting.py`
- Test: `MBM/LeadEngine/real_estate/tests/test_underwriting.py`

**Interfaces:**
- `underwrite(arv: float, repairs: float, purchase_price: float, assignment_fee_target: float = 15000.0) -> dict[str, object]`
- `qualifies_for_human_review(underwriting: dict[str, object], source_status: str, contact_verified: bool) -> bool`

- [ ] **Step 1: Write the failing test**

```python
def test_underwrite_calculates_mao_from_seventy_percent_rule():
    result = underwrite(arv=200000, repairs=30000, purchase_price=70000)
    assert result["mao"] == 110000
    assert result["gross_spread"] == 130000
    assert result["passes_economic_gate"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_underwriting.py::test_underwrite_calculates_mao_from_seventy_percent_rule -v`
Expected: FAIL because `underwrite` does not exist.

- [ ] **Step 3: Write minimal implementation**

Use `mao = max(0, arv * 0.70 - repairs)`. Return explicit fields for ARV, repairs, purchase price, MAO, gross spread, projected assignment fee, and gate state. The gate must require a positive purchase-to-MAO margin, non-blocked source status, and verified contact data.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_underwriting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate/underwriting.py MBM/LeadEngine/real_estate/tests/test_underwriting.py
git commit -m "feat: add deterministic real-estate underwriting gate"
```

---

### Task 3: Offer generation and manual-channel handoff

**Files:**
- Create: `MBM/LeadEngine/real_estate/offer_builder.py`
- Test: `MBM/LeadEngine/real_estate/tests/test_offer_builder.py`

**Interfaces:**
- `build_offer_packet(property_evidence: PropertyEvidence, seller: dict[str, object], buyer: BuyerEvidence | None, underwriting: dict[str, object], offer_price: float) -> OfferPacket`
- `build_email_copy(...) -> str`
- `build_whatsapp_copy(...) -> str`
- `build_call_payload(...) -> dict[str, object]`

- [ ] **Step 1: Write the failing test**

```python
def test_build_offer_packet_contains_copy_ready_channels_without_sending():
    packet = build_offer_packet(PROPERTY, SELLER, BUYER, UNDERWRITING, 85000)
    assert "85000" in packet.email_copy
    assert "85,000" in packet.whatsapp_copy
    assert packet.manual_call_payload["phone"] == "+12165550123"
    assert packet.send_state == "HUMAN_SEND_REQUIRED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_offer_builder.py::test_build_offer_packet_contains_copy_ready_channels_without_sending -v`
Expected: FAIL because the builder does not exist.

- [ ] **Step 3: Write minimal implementation**

Generate factual, non-deceptive channel copy from supplied evidence only. Do not claim ownership, valuation, urgency, or cash capability unless represented in the evidence. Set `send_state = "HUMAN_SEND_REQUIRED"` and never call an external messaging provider.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_offer_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate/offer_builder.py MBM/LeadEngine/real_estate/tests/test_offer_builder.py
git commit -m "feat: build copy-ready real-estate offer packets"
```

---

### Task 4: Scrapling evidence adapter

**Files:**
- Create: `MBM/LeadEngine/real_estate/scrapling_adapter.py`
- Test: `MBM/LeadEngine/real_estate/tests/test_scrapling_adapter.py`

**Interfaces:**
- `normalize_scrapling_record(record: dict[str, object]) -> PropertyEvidence`
- `normalize_scrapling_batch(records: list[dict[str, object]]) -> list[PropertyEvidence]`

- [ ] **Step 1: Write the failing test**

```python
def test_normalize_scrapling_record_preserves_source_and_explicit_status():
    result = normalize_scrapling_record({
        "url": "https://example.com/property/1",
        "source": "example",
        "status": "ok",
        "address": "123 Main St",
        "city": "Cleveland",
        "state": "OH",
    })
    assert result.source_url == "https://example.com/property/1"
    assert result.status == "ok"
    assert result.address == "123 Main St"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_scrapling_adapter.py::test_normalize_scrapling_record_preserves_source_and_explicit_status -v`
Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Write minimal implementation**

Map common Scrapling output fields into the stable evidence contract. Reject fabricated or missing provenance. Batch normalization must preserve blocked/empty/malformed rows rather than dropping them silently.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_scrapling_adapter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate/scrapling_adapter.py MBM/LeadEngine/real_estate/tests/test_scrapling_adapter.py
git commit -m "feat: normalize Scrapling property evidence"
```

---

### Task 5: MBM canonical deal bridge and runnable entry point

**Files:**
- Create: `MBM/LeadEngine/real_estate/deal_bridge.py`
- Create: `MBM/LeadEngine/real_estate/offer_cli.py`
- Create: `MBM/LeadEngine/real_estate/tests/test_deal_bridge.py`
- Modify: `package.json`

**Interfaces:**
- `to_canonical_deal(packet: OfferPacket) -> CanonicalDeal`
- CLI command: `python -m MBM.LeadEngine.real_estate.offer_cli --input <json> --output <json>`
- Package script: `"deals:offer": "python MBM/LeadEngine/real_estate/offer_cli.py --input examples/real_estate_offer.json --output artifacts/real_estate_offer_packet.json"`

- [ ] **Step 1: Write the failing test**

```python
def test_bridge_maps_offer_packet_into_canonical_deal():
    deal = to_canonical_deal(PACKET)
    assert deal.deal_type == DealType.PROPERTY
    assert deal.stage == DealStage.QUALIFIED
    assert deal.primary_offer == "$85,000"
    assert deal.contact_phone == "+12165550123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_deal_bridge.py::test_bridge_maps_offer_packet_into_canonical_deal -v`
Expected: FAIL because `to_canonical_deal` does not exist.

- [ ] **Step 3: Write minimal implementation**

Populate the existing `CanonicalDeal` without changing its schema. Preserve evidence provenance and map stage to `QUALIFIED` only when the underwriting gate passes; otherwise use `NEW` with `next_action=VERIFY_DEAL`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_deal_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate/deal_bridge.py MBM/LeadEngine/real_estate/offer_cli.py MBM/LeadEngine/real_estate/tests/test_deal_bridge.py package.json
git commit -m "feat: bridge real-estate offers into canonical deal memory"
```

---

### Task 6: Verify the end-to-end slice

**Files:**
- Test: `MBM/LeadEngine/real_estate/tests/test_e2e_offer_flow.py`
- Create: `examples/real_estate_offer.json`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
def test_e2e_flow_produces_manual_send_packet_and_call_handoff():
    packet = run_fixture("examples/real_estate_offer.json")
    assert packet["send_state"] == "HUMAN_SEND_REQUIRED"
    assert packet["manual_call_payload"]["phone"]
    assert packet["source_provenance"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest MBM/LeadEngine/real_estate/tests/test_e2e_offer_flow.py -v`
Expected: FAIL until the CLI/bridge/fixture are wired together.

- [ ] **Step 3: Wire the fixture and runnable entry point**

Use only synthetic example data in the repository fixture. Document that production data must come from approved public/property sources or connected prospecting systems and that the user remains the sender/caller.

- [ ] **Step 4: Run tests**

Run: `pytest MBM/LeadEngine/real_estate/tests -q`
Expected: PASS for all new tests.

Run: `python MBM/LeadEngine/real_estate/offer_cli.py --input examples/real_estate_offer.json --output artifacts/real_estate_offer_packet.json`
Expected: exit code 0 and a JSON packet with email, WhatsApp, and call handoff content.

- [ ] **Step 5: Commit**

```bash
git add MBM/LeadEngine/real_estate/tests/test_e2e_offer_flow.py examples/real_estate_offer.json README.md
git commit -m "test: verify real-estate offer flow end to end"
```
