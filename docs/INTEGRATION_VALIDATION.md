# Intelligence Layer + Reward Clipping Integration Validation

## 1. System State Freeze
- **Branch**: `master`
- **Commit SHA**: `393cea8c64111d8d5585bdd5efb7efd69c0474a3`

## 2. Changes Reviewed
The integration focused purely on safe boundaries, affecting the following files:
- `MBM/LeadEngine/intelligence/types.py`
- `MBM/LeadEngine/intelligence/opportunity_engine.py`
- `MBM/LeadEngine/intelligence/opportunity_queue.py`
- `MBM/LeadEngine/intelligence/content_orchestrator.py`
- `MBM/LeadEngine/intelligence/world_monitor_adapter.py`
- `MBM/LeadEngine/intelligence/tests/test_live_contracts.py`
- `MBM/LeadEngine/intelligence/tests/test_pipeline_isolation.py`

## 3. Architecture Boundaries Verified
The Intelligence layer sits strictly as a decision-support layer above the existing execution systems (`LeadEngine` and `MBM-Social`).
- **Intelligence** -> produces `Opportunity` objects.
- **Opportunity Queue** -> stores opportunities as a side-car (`opportunities.json`).
- **Execution** -> retains its own safety contracts and requires explicit approval to process the queue.

## 4. Opportunity Queue Contract
The Opportunity Queue acts as the human-in-the-loop decision boundary.
- **Workflow**: `DISCOVER` -> `NORMALIZE` -> `SCORE` -> `QUEUE` -> `REVIEW`
- Opportunities are written to `MBM/Artifacts/intelligence/opportunities.json`. 
- No automated actions bypass this queue.

## 5. Provenance Contract
Every externally-derived event must include complete provenance.
- Required fields: `provider`, `captured_at`, `transformation_lineage`, `source_url`.
- Legacy instantiation paths (e.g. `retrievedAt`) have been eradicated.
- Missing provenance automatically sets the opportunity status to `REVIEW_REQUIRED`.

## 6. LeadEngine & Reward Clipping Isolation Evidence
- **Static Search**: Validated that `LeadEngine` mutation logic, dialer state, and outreach functions have ZERO dependencies on the new `intelligence` modules. No hidden imports were found.
- **Dynamic Tests**: `test_pipeline_isolation.py` explicitly proves that invoking the `ContentOrchestrator` does NOT instantiate or call `DialerSingleWriter` and makes zero modifications to `leads_database.json`.
- **Clipping Firewall**: Intelligence does not download or publish. It merely recommends opportunities for the Clipping Pipeline to eventually act on post-approval.

## 7. Dry-Run Behavior
The orchestrator supports a dry-run flag (`create_drafts=False`). In this mode, discovery, normalization, and scoring proceed normally, but NO disk mutations or external writes occur.

## 8. Live-Test Policy
Live contract tests (`test_live_contracts.py`) are strictly opt-in using the `@pytest.mark.live` marker. If API keys are not present in the environment, the tests fail closed (or skip gracefully), guaranteeing they will not inadvertently execute on CI.

## 9. Provider Capability Matrix
- **World Monitor**: `READ` = yes, `WRITE` = no
- **Anderro / Topview / SkySnail**: `READ` = yes, `SUBMIT` = conditional (blocked at queue level)
- *Never infer write capability from read capability.*

## 10. Test Commands & Results
```bash
$env:PYTHONPATH=".;clipping-factory/MBM-Social"

python -m pytest MBM/LeadEngine/intelligence/tests -q
# Result: 26 passed, 4 skipped (live), 1 warning (1.88s)

python -m pytest MBM/LeadEngine/tests/test_dialer_integrity_gate.py -q
# Result: 15 passed (23.76s)

python -m pytest clipping-factory/MBM-Social/tests/test_reward_clipping_regression.py -q
# Result: 3 passed (1.27s)
```

## 11. Known Limitations & Remaining Risks
- **Limitation**: The system currently lacks a UI or CLI command for a human to bulk-approve opportunities from `opportunities.json`.
- **Risk**: Live rate limits from Topview/World Monitor are untested under load because live execution is paused.

## 12. Recommended Next Phase
**Phase: Human Review Interface & Read-Only Live Trials**
We recommend building a lightweight interface (CLI or Web) to let operators safely review the `opportunities.json` queue. Once this is done, we can enable live API credentials for *discovery only*, proving the system end-to-end without risking automated writes.
