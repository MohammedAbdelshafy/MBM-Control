"""Deployment bridge (P0.10).

Local-first: every control-plane worker runs in-process today. This module
makes the SAME worker deployable to Cloud Run (default for independently
useful services) and, where justified, Agent Engine — via environment-based
config, secret *references* (never values), least-privilege service
accounts, health checks, structured logs, explicit resource limits, and
safe defaults.

No cloud migration happens here. This module only *probes readiness* and
*generates* safe-default specs so a future move is mechanical.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class DeploymentTarget(str, Enum):
    LOCAL = "local"
    CLOUD_RUN = "cloud_run"
    AGENT_ENGINE = "agent_engine"


@dataclass
class ReadinessItem:
    check: str
    passed: bool
    detail: str


@dataclass
class ReadinessReport:
    target: DeploymentTarget
    ready: bool
    items: List[ReadinessItem] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.value,
            "ready": self.ready,
            "items": [{"check": i.check, "passed": i.passed, "detail": i.detail} for i in self.items],
            "blockers": self.blockers,
        }


def load_env_config(env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Environment-based configuration. Returns names/values for NON-secret
    config only; secret material is referenced by name (see secret_refs)."""
    env = env or os.environ
    return {
        "JARVIS_MODE": env.get("JARVIS_MODE", "local"),
        "JARVIS_DRY_RUN": env.get("JARVIS_DRY_RUN", "true"),
        "MBM_ARTIFACTS_ROOT": env.get("MBM_ARTIFACTS_ROOT", "MBM/Artifacts"),
        "LOG_LEVEL": env.get("LOG_LEVEL", "INFO"),
    }


def secret_refs() -> List[str]:
    """Secret NAMES the runtime expects from the environment/secret manager.
    Values are never read here, never logged, never embedded in specs."""
    return [
        "PHOUND_TOKEN",
        "PHOUND_PERSONAS",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "GITHUB_TOKEN",
        "SUPABASE_SERVICE_ROLE_KEY",
    ]


def readiness_probe(
    target: DeploymentTarget, env: Optional[Mapping[str, str]] = None
) -> ReadinessReport:
    env = dict(env or os.environ)
    items: List[ReadinessItem] = []
    blockers: List[str] = []

    def check(name: str, ok: bool, detail: str, blocks: bool = True) -> None:
        items.append(ReadinessItem(name, ok, detail))
        if not ok and blocks:
            blockers.append(name)

    # Local is always deployable: in-process, DRY_RUN default, file state.
    check("local_runtime", True, "in-process worker; DRY_RUN default; file-backed state")

    if target in (DeploymentTarget.CLOUD_RUN, DeploymentTarget.AGENT_ENGINE):
        check(
            "service_account",
            bool(env.get("JARVIS_SERVICE_ACCOUNT")),
            "dedicated least-privilege service account (JARVIS_SERVICE_ACCOUNT)",
        )
        check(
            "secret_manager",
            bool(env.get("JARVIS_SECRET_MANAGER", "")),
            "secrets via manager reference, none embedded (JARVIS_SECRET_MANAGER)",
        )
        check(
            "health_endpoint",
            True,
            "GET /healthz required on the worker (contract; wire in adapter)",
            blocks=False,
        )
        check(
            "resource_limits",
            True,
            "see cloud_run_service_spec() safe defaults (cpu/mem/concurrency/timeout)",
            blocks=False,
        )
    if target is DeploymentTarget.AGENT_ENGINE:
        check(
            "agent_justification",
            bool(env.get("JARVIS_AGENT_ENGINE_JUSTIFIED") == "true"),
            "Agent Engine only where managed-agent capabilities materially justify it",
        )
    return ReadinessReport(target=target, ready=not blockers, items=items, blockers=blockers)


def cloud_run_service_spec(service_name: str, image: str = "jarvis-worker:latest") -> Dict[str, Any]:
    """Safe-default Cloud Run service spec (dict; render to YAML at deploy time).
    Contains zero secrets — only references."""
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {"name": service_name},
        "spec": {
            "template": {
                "metadata": {"annotations": {"autoscaling.knative.dev/maxScale": "4"}},
                "spec": {
                    "serviceAccountName": "${JARVIS_SERVICE_ACCOUNT}",
                    "timeoutSeconds": 300,
                    "containerConcurrency": 8,
                    "containers": [
                        {
                            "image": image,
                            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                            "ports": [{"containerPort": 8080}],
                            "env": [
                                {"name": "JARVIS_MODE", "value": "cloud_run"},
                                {"name": "JARVIS_DRY_RUN", "value": "true"},
                            ],
                        }
                    ],
                },
            }
        },
    }
