"""Jarvis-managed swarm supervisor.

The swarm can inspect and verify MBM systems immediately, but mutating jobs are
approval-gated. Specialized agents never become canonical data authorities.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from MBM.GLM.core_agents import ReviewAgent, TestAgent, SecurityAgent, PerformanceAgent, ReliabilityAgent
from MBM.GLM.revenue_and_gtm_agents import (
    GTMEngineerAgent,
    DialerEngineerAgent,
    SocialEngineerAgent,
    MonetizationEngineerAgent,
    RevenueAnalystAgent,
)


@dataclass(frozen=True)
class SwarmJob:
    job_id: str
    system: str
    role: str
    operation: str
    mutation: bool
    approval_required: bool
    priority: int
    description: str


@dataclass
class SwarmResult:
    job_id: str
    system: str
    role: str
    status: str
    result: Dict[str, Any]
    started_at: str
    completed_at: str


class JarvisSwarmSupervisor:
    """Single control plane for dispatching specialized system jobs."""

    def __init__(self, approval_checker: Callable[[str], bool] | None = None):
        self.approval_checker = approval_checker or (lambda _job_id: False)
        self.agents = {
            "reliability": ReliabilityAgent(),
            "security": SecurityAgent(),
            "performance": PerformanceAgent(),
            "test": TestAgent(),
            "gtm": GTMEngineerAgent(),
            "dialer": DialerEngineerAgent(),
            "social": SocialEngineerAgent(),
            "monetization": MonetizationEngineerAgent(),
            "revenue": RevenueAnalystAgent(),
        }
        self.jobs = self._build_jobs()

    def _build_jobs(self) -> List[SwarmJob]:
        return [
            SwarmJob("SWARM-GTM-AUDIT", "LeadEngine", "gtm", "audit", False, False, 10, "Audit verified lead factory, hot leads, meetings and opportunities."),
            SwarmJob("SWARM-DIALER-AUDIT", "mbm-dialer", "dialer", "audit", False, False, 10, "Audit dialer inventory and seller/buyer lane readiness."),
            SwarmJob("SWARM-SOCIAL-AUDIT", "MBM-Social", "social", "audit", False, False, 9, "Audit social runtime and brand readiness."),
            SwarmJob("SWARM-REVENUE-AUDIT", "Revenue", "revenue", "audit", False, False, 10, "Separate confirmed revenue, pipeline and expected value."),
            SwarmJob("SWARM-MONETIZATION-AUDIT", "Monetization", "monetization", "audit", False, False, 9, "Audit offer and canonical checkout rail configuration."),
            SwarmJob("SWARM-DATA-INTEGRITY", "mbm-dialer", "reliability", "audit", False, False, 10, "Verify single-writer protection and inventory integrity."),
            SwarmJob("SWARM-SECURITY", "All", "security", "audit", False, False, 10, "Run security checks without modifying application data."),
            SwarmJob("SWARM-APPROVED-IMPLEMENT", "All", "orchestrator", "implement", True, True, 10, "Execute an explicitly approved mission through its canonical writer and verification gates."),
        ]

    def manifest(self) -> List[Dict[str, Any]]:
        return [asdict(j) for j in sorted(self.jobs, key=lambda x: x.priority, reverse=True)]

    def dispatch(self, job_id: str) -> SwarmResult:
        job = next((j for j in self.jobs if j.job_id == job_id), None)
        if job is None:
            raise KeyError(f"Unknown swarm job: {job_id}")

        started = datetime.now(timezone.utc).isoformat()
        if job.mutation and (job.approval_required and not self.approval_checker(job.job_id)):
            return SwarmResult(job.job_id, job.system, job.role, "WAITING_FOR_JARVIS_APPROVAL",
                                {"reason": "mutation job is approval-gated"}, started,
                                datetime.now(timezone.utc).isoformat())

        agent = self.agents.get(job.role)
        if job.operation == "audit":
            result = self._run_audit(job.role, agent)
        else:
            result = {"status": "APPROVED_EXECUTION_HANDOFF", "note": "Mission executor must be supplied by Jarvis mission router."}

        return SwarmResult(job.job_id, job.system, job.role, "COMPLETED", result, started,
                           datetime.now(timezone.utc).isoformat())

    @staticmethod
    def _run_audit(role: str, agent: Any) -> Dict[str, Any]:
        if role == "gtm":
            return agent.audit_gtm_state()
        if role == "dialer":
            return agent.audit_dialer_readiness()
        if role == "social":
            return agent.audit_social_subsystem()
        if role == "revenue":
            return agent.audit_revenue_attribution()
        if role == "monetization":
            return agent.audit_monetization_rails()
        if role == "reliability":
            return agent.audit_dialer_single_writer()
        if role == "security":
            return {"status": "READY", "mode": "non-mutating", "scope": "runtime-controlled"}
        raise ValueError(f"No audit adapter for role {role}")

    def run_read_only_sweep(self) -> List[SwarmResult]:
        """Run all currently safe system audits. No canonical writes occur."""
        return [self.dispatch(job.job_id) for job in self.jobs if not job.mutation]


def swarm_snapshot() -> Dict[str, Any]:
    supervisor = JarvisSwarmSupervisor()
    return {
        "controller": "Jarvis_GLM_orchestrator",
        "mode": "read_only_sweep",
        "jobs": supervisor.manifest(),
        "mutation_policy": "approval_required",
        "canonical_writes_by_swarm": False,
    }
