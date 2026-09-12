"""JARVIS control plane — governed multi-agent substrate (P0).

JARVIS remains the top-level decider. This package is the workflow/control
layer underneath it: explicit 7-phase workflow state, central policy,
machine-readable agent registry, record/replay, trajectory evaluation,
isolated state scopes, MCP/A2A boundaries, and deployment readiness.

It wraps existing systems (MBM/GLM/*, MBM/LeadEngine/*, server/dialer/*)
and creates no competing sources of truth.
"""

from .workflow import (
    WorkflowPhase,
    WorkflowRun,
    InvalidWorkflowTransitionError,
    start_run,
)
from .policy import (
    ActionClass,
    PolicyVerdict,
    PolicyDecision,
    classify,
    evaluate,
    redact,
    resolve_class,
    new_correlation_id,
    retry_allowed,
)
from .registry import (
    AgentProtocol,
    AgentHealth,
    ControlPlaneAgentSpec,
    build_registry,
)
from .record_replay import RunMode, RunEvent, RunRecorder, ReplayHarness
from .evaluation import ExpectedStep, TrajectoryVerdict, evaluate_trajectory
from .state import StateScope, IsolatedStateStore, CanonicalLeadStore
from .mcp_a2a import MCPToolBus, MCPToolDefinition, MCPPermissionDenied, expose_specialist_as_tool, A2AMessage, A2AMesh
from .telemetry import InMemorySink, NoOpSink, TelemetryEvent, TelemetrySink, new_trace_id, timed
from .deploy import DeploymentTarget, readiness_probe, cloud_run_service_spec
from .capabilities import build_capability_bus

__version__ = "0.1.0"

__all__ = [
    "WorkflowPhase",
    "WorkflowRun",
    "InvalidWorkflowTransitionError",
    "start_run",
    "ActionClass",
    "PolicyVerdict",
    "PolicyDecision",
    "classify",
    "evaluate",
    "redact",
    "resolve_class",
    "new_correlation_id",
    "retry_allowed",
    "AgentProtocol",
    "AgentHealth",
    "ControlPlaneAgentSpec",
    "build_registry",
    "RunMode",
    "RunEvent",
    "RunRecorder",
    "ReplayHarness",
    "ExpectedStep",
    "TrajectoryVerdict",
    "evaluate_trajectory",
    "StateScope",
    "IsolatedStateStore",
    "CanonicalLeadStore",
    "MCPToolBus",
    "MCPToolDefinition",
    "MCPPermissionDenied",
    "expose_specialist_as_tool",
    "A2AMessage",
    "A2AMesh",
    "InMemorySink",
    "NoOpSink",
    "TelemetryEvent",
    "TelemetrySink",
    "new_trace_id",
    "timed",
    "DeploymentTarget",
    "readiness_probe",
    "cloud_run_service_spec",
    "build_capability_bus",
]
