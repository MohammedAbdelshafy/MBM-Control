# MBM-Control Source of Truth

## Canonical Hierarchy

```
MBM-Control
│
├── LeadEngine
│   └── lead-generation / verification / queue authority
│
├── MBM-Social
│   └── social / clipping execution authority
│
├── Intelligence
│   └── research / normalization / scoring / provenance
│
└── Spec-Ad Engine
    └── account → creative → QA → orchestration
```

Repository orchestration does NOT imply subsystem ownership.
Every subsystem retains a clear data and write authority.

## Knowledge-Graph Contract

The MBM Control Knowledge Graph serves as an architectural index. It must represent the following hierarchy:

```
MBM-Control
    ↓
GitHub Control Plane
    ↓
LeadEngine
    ↓
Intelligence
    ↓
Spec-Ad Engine
    ↓
Creative / Video / QA
    ↓
Outreach Boundary
    ↓
Funnel Metrics
    ↓
Creative Learning
```

### Relationship Types
- `depends_on`: Component reliance on another module or data source.
- `protects`: Safety and compliance gating.
- `extends`: Augmentation of existing capabilities.
- `reads_from`: Data ingestion vectors.
- `writes_to`: State mutation authority.
- `gates`: Pre-execution validation.
- `learns_from`: Feedback loops for optimization.
- `synchronized_by`: Remote state reconciliation operations.

*Note: The graph is an explanatory/control map, not a runtime database and must never become a second source of truth.*
