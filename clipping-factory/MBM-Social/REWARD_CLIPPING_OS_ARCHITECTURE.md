# Reward Clipping OS Architecture

## Overview
The Reward Clipping OS is a deterministic campaign qualification and reward allocation engine. It sits upstream of the MBM-Social publisher. Its primary purpose is to act as a **planning and qualification system**, ensuring that clips produced for third-party marketplace campaigns (e.g., Whop) are economically viable, mathematically sound, and brand-safe before any production effort is expended.

## Core Tenets
1. **No-Publish Invariant**: The Reward Clipping OS does **not** publish content. It plans, scores, and qualifies clips. Publishing is strictly handled by the existing MBM-Social downstream publishing governance. "Produce" means the clip is qualified for production, not that it is automatically published.
2. **Economic Hardening**: All economic formulas fail closed. Profitability is evaluated against worst-case fallback scenarios. Division-by-zero, NaN, infinite values, negative payouts, and exceeded budgets immediately trip a hard rejection gate.
3. **Immutability and Provenance**: Every entity generated (Source -> Moment -> Clip Plan -> Economic Projection -> QA Result) maintains a strict cryptographic lineage to its upstream source via deterministic hashing (`source_id`, `moment_id`, etc.). This prevents platform drift and ensures full auditability.

## Pipeline Phases
1. **Source Registry**: Immutable tracking of video source files (`NormalizedSource`).
2. **Moment Discovery**: AI and rule-based generation of candidate clip moments (`CandidateMoment`). Fallback rules (e.g. cold open) must explicitly identify themselves and yield low-to-medium confidence, triggering mandatory human review.
3. **Clip Planning**: Generating a `ClipPlan` that targets platform constraints (e.g., TikTok < 60s, YouTube Shorts < 60s). Network isolation is strictly enforced; planning cannot trigger API calls.
4. **Economic Evaluation**: Three-scenario mathematical projection (Pessimistic, Base, Optimistic).
5. **QA Gates**: Deterministic evaluation. 
    - Gate A: Source Integrity
    - Gate B: Moment Integrity
    - Gate C: Clip Plan Integrity
    - Gate D: Production Safety
    - Gate E: Economic Safety

Any hard failure triggers a `REJECT`. Low confidence or low margins trigger a `REVIEW_REQUIRED`. Only perfect passes yield `PRODUCE`.
