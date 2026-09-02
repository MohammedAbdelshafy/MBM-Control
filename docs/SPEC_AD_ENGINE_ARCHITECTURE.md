# Spec-Ad Engine Architecture (Phase 1)

## Overview
The Spec-Ad Engine serves as the orchestration layer connecting the Intelligence subsystem with Creative execution.

**Phase 1 constraints strictly enforced:**
- **No live provider calls**
- **No outreach execution**
- **No CRM writes**
- **No autonomous spending**

## Architecture Components

### 1. Account Selection & Readiness (Read-Only)
Identifies accounts based on Intelligence output and opportunity scores. Acts as a read-only consumer of `opportunities.json`.

### 2. Creative Orchestration (Scaffolding)
Maps accounts to proposed creative variants. All operations execute in a dry-run/planning state without rendering or dispatching jobs.

### 3. QA / Human-in-the-Loop Airlock
All generated plans are deposited into an airlock queue. Explicit human approval is required to progress to Phase 2 (execution).

## Future (Phase 2 - DO NOT SCAFFOLD)
Phase 2 will introduce TargetAccount scoring, active generation, CRM writes, and SQL persistence (00020_spec_ad_engine.sql).
