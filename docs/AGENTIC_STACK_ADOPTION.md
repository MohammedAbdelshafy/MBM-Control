# Agentic Stack Adoption

## Adopted source projects
- DeusData/codebase-memory-mcp: persistent repository knowledge graph for coding agents.
- codegraph-ai/CodeGraph: semantic code relationships and impact analysis.
- msitarzewski/agency-agents: curated specialist role/workflow patterns.
- calesthio/OpenMontage: agentic video-production capabilities.

## Governance
These sources augment MBM; they do not replace the Constitution, EventBus/MissionQueue, release gates, airlocks, or single-writer controls.

## Boundaries
1. Codebase Memory is the preferred persistent engineering-context capability.
2. CodeGraph is used for semantic/impact analysis and benchmarked against overlapping Codebase Memory features.
3. Agency Agents is treated as a curated role library, not an autonomous authority.
4. OpenMontage is an external video capability source. Its AGPL-3.0 license requires review before code reuse in proprietary components.

## Safety / integrity
- No direct specialist writes to lead databases.
- No bypass of DialerSingleWriter.
- Intelligence layers remain non-publishing unless an explicit governed mission authorizes the action.
- Optional providers must fail soft and never become single points of failure.
