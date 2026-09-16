# Commercial Radar Slice A — offline scope

Implementation: `MBM/ContecRadar/slice_a.py`
Tests: `MBM/ContecRadar/tests/test_slice_a.py`

Slice A ingests in-memory signal dicts, clusters/scores/decides via the
existing deterministic ContecRadar engines, and returns ranked opportunities.

Exclusions preserved (fail-closed `ExcludedOperationError`):

- no outbound sending (`send_outreach` raises)
- no campaign execution (`execute_campaign` raises)
- no external DB/runtime mutation (`mutate_external_db` raises)
- no autonomous approval queue (`autonomous_approve` raises)
- no demo-generation scope creep (`generate_demo` raises)

No network, filesystem writes, or external side effects.
Timestamps are wall-clock evidence markers; commercial determinism is
scores/decisions/titles (see test `_stable` helper).
