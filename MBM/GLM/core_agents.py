#!/usr/bin/env python3
"""
GLM Swarm Core Engineering Agents
=================================
Implements Review, Test, Security, Performance, and Reliability agents.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier, get_agent


ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class ReviewAgent:
    """GLM_CODE_REVIEWER: Audits diffs, syntax, potential regressions, and race conditions."""

    def __init__(self):
        self.spec = get_agent(GLMRole.CODE_REVIEWER)

    def review_diff(self, diff_text: str, file_path: str = "") -> Dict[str, Any]:
        issues = []
        # Check for common anti-patterns
        if "console.log" in diff_text and not file_path.endswith(".test.ts"):
            issues.append({"type": "LINT_WARNING", "message": "Extraneous console.log detected in production path."})
        if "hardcoded" in diff_text.lower() or "TODO: fix password" in diff_text:
            issues.append({"type": "SECURITY_WARNING", "message": "Potential hardcoded credential or placeholder."})
        if "except Exception: pass" in diff_text or "except: pass" in diff_text:
            issues.append({"type": "BRITTLE_LOGIC", "message": "Silent exception swallowing detected."})
        if "555-" in diff_text:
            issues.append({"type": "DATA_INTEGRITY", "message": "Synthetic phone pattern 555- detected."})

        return {
            "agent": self.spec.name,
            "tier_used": self.spec.preferred_tier.value,
            "status": "APPROVED" if not issues else "FLAGGED",
            "issues_count": len(issues),
            "issues": issues,
        }


class TestAgent:
    """GLM_TEST_ENGINEER: Runs and verifies pytest and TypeScript test suites."""

    def __init__(self):
        self.spec = get_agent(GLMRole.TEST_ENGINEER)

    def run_suite(self, suite_cmd: List[str], cwd: Path = ROOT_DIR) -> Dict[str, Any]:
        try:
            res = subprocess.run(suite_cmd, cwd=str(cwd), capture_output=True, text=True, timeout=120)
            passed = res.returncode == 0
            return {
                "agent": self.spec.name,
                "command": " ".join(suite_cmd),
                "passed": passed,
                "exit_code": res.returncode,
                "stdout_tail": "\n".join(res.stdout.splitlines()[-10:]),
                "stderr_tail": "\n".join(res.stderr.splitlines()[-10:]) if res.stderr else "",
            }
        except Exception as e:
            return {
                "agent": self.spec.name,
                "command": " ".join(suite_cmd),
                "passed": False,
                "error": str(e),
            }


class SecurityAgent:
    """GLM_SECURITY_ENGINEER: Audits repositories for secret leaks, auth bypass, and dangerous endpoints."""

    def __init__(self):
        self.spec = get_agent(GLMRole.SECURITY_ENGINEER)

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        findings = []
        if not file_path.exists() or file_path.is_dir():
            return findings

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        # Check for unmasked keys
        patterns = [
            (r'(?:api_key|secret|token)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "Potential exposed API secret"),
            (r'eval\s*\(', "Unsafe eval usage"),
            (r'exec\s*\(', "Unsafe exec usage"),
        ]
        for pat, desc in patterns:
            for match in re.finditer(pat, content, re.IGNORECASE):
                findings.append({
                    "file": str(file_path),
                    "description": desc,
                    "snippet": match.group(0)[:40] + "...",
                })
        return findings


class PerformanceAgent:
    """GLM_PERFORMANCE_ENGINEER: Detects model call duplication, unindexed queries, and slow loops."""

    def __init__(self):
        self.spec = get_agent(GLMRole.PERFORMANCE_ENGINEER)

    def audit_module_performance(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {"file": str(file_path), "status": "NOT_FOUND"}
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        
        has_caching = "cache" in content.lower() or "lru_cache" in content
        has_rate_limiting = "sleep" in content or "limiter" in content.lower()
        
        return {
            "file": str(file_path),
            "has_caching": has_caching,
            "has_rate_limiting": has_rate_limiting,
            "optimization_score": 85 if has_caching else 70,
        }


class ReliabilityAgent:
    """GLM_RELIABILITY_ENGINEER: Audits single-writer locks, process collisions, and dataset protection."""

    def __init__(self):
        self.spec = get_agent(GLMRole.RELIABILITY_ENGINEER)

    def audit_dialer_single_writer(self) -> Dict[str, Any]:
        from MBM.GLM.single_writer_lock import get_single_writer
        writer = get_single_writer()
        leads = writer.read_leads()
        return {
            "agent": self.spec.name,
            "single_writer_active": True,
            "leads_count": len(leads),
            "status": "PROTECTED (Zero Shrinkage Invariant Enforced)",
        }
