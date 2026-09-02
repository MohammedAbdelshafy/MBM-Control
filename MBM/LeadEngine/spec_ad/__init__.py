"""
MBM LeadEngine — Spec-Ad Orchestration Layer (Phase 2)

This package is the business/orchestration layer for the Spec-Ad Sales Engine.
It sits on top of LeadEngine and Intelligence, consuming their services via
adapters. It does NOT duplicate LeadEngine, clipping factory, email sender,
queue framework, CRM, or suppression DB.

Phase 1 architecture is complete; Phase 2 implements the target-account
foundation: config → dedup → scoring → repository.

Runtime decision (Step 1): Python.
- LeadEngine canonical code is Python (dialer_verification_gate.py, dialer_queue_engine.py,
  intelligence/*, property_intel/*, single_writer_lock.py).
- intelligence/config.py and types.py use dataclasses + env flags; spec_ad follows same.
- Previous JS scaffold at spec-ad-engine/src/ is staging/still present for reference; the
  production implementation lives here. No Python/Node bridge introduced; if a Node
  caller needs targeting, it must import via a thin adapter, not duplicate logic.

Ownership: Terminal 1 — MBM/LeadEngine/spec_ad/config/, targeting/, tests/ only in Phase 2.
"""

__all__ = ["config", "targeting"]
