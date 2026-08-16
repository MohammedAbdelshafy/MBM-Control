"""
TESTS: MBM GTM AGENTS & BOTS MONITORING AND CREATION SUPERVISOR
=============================================================================
Hermetic unit tests verifying:
1. GtmAgentSupervisor initialization and lifecycle
2. Process & Terminal Watchdog metrics (CPU, RAM, OpenCode detection)
3. Hunter, Outreach, Closer, and Content Creator agent executions
4. Canonical Neteller checkout rail injection into packaged campaigns
5. JSON & Markdown report exports
6. Telegram monitoring alert formatting
=============================================================================
"""

import os
import json
import pytest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_agent_supervisor import GtmAgentSupervisor, ARTIFACTS_DIR


def test_gtm_agent_supervisor_initialization():
    """Verify supervisor instantiates with clean initial state and timestamp."""
    supervisor = GtmAgentSupervisor(run_mode="all")
    assert supervisor.run_mode == "all"
    assert supervisor.report_data["status"] == "HEALTHY"
    assert "timestamp" in supervisor.report_data


def test_process_watchdog_monitoring():
    """Verify watchdog correctly inspects system health and detects active processes."""
    supervisor = GtmAgentSupervisor()
    procs = supervisor.monitor_processes()
    
    assert isinstance(procs, list)
    health = supervisor.report_data["system_health"]
    assert "cpu_percent" in health
    assert "ram_percent" in health
    assert "ram_used_gb" in health
    assert "active_worker_count" in health
    assert health["active_worker_count"] == len(procs)


def test_gtm_hunter_agent_execution():
    """Verify Hunter agent evaluates buyer signals and populates hunter stats."""
    supervisor = GtmAgentSupervisor()
    stats = supervisor.run_hunter_agent()
    
    assert "hot_buyers" in stats
    assert "high_intent" in stats
    assert supervisor.report_data["agents"]["hunter"] == stats


def test_gtm_outreach_creator_and_neteller_rail():
    """Verify Outreach agent packages campaigns with canonical Neteller links."""
    supervisor = GtmAgentSupervisor()
    stats = supervisor.run_outreach_creator_agent()
    
    assert "campaign_id" in stats
    assert "deals_packaged" in stats
    
    campaigns = supervisor.report_data["campaigns_created"]
    assert isinstance(campaigns, list)
    
    for c in campaigns:
        assert "neteller_checkout" in c
        assert "member.neteller.com/pay" in c["neteller_checkout"]
        assert "abdelshafyclapps%40gmail.com" in c["neteller_checkout"]
        assert "4599228811" in c["neteller_checkout"]
        assert "sku" in c
        assert "retainer_usd" in c


def test_gtm_closer_and_creator_agents():
    """Verify Closer CRM sync and Content Creator factory status."""
    supervisor = GtmAgentSupervisor()
    closer_stats = supervisor.run_closer_crm_agent()
    creator_stats = supervisor.run_content_creation_agent()
    
    assert closer_stats["crm_status"] == "IDEMPOTENT_SYNCED"
    assert "brands_active" in creator_stats
    assert len(creator_stats["brands_active"]) >= 3


def test_gtm_report_export_and_artifacts():
    """Verify GTM report generator writes valid JSON and Markdown artifacts."""
    supervisor = GtmAgentSupervisor()
    supervisor.monitor_processes()
    supervisor.run_hunter_agent()
    supervisor.run_outreach_creator_agent()
    supervisor.run_closer_crm_agent()
    supervisor.run_content_creation_agent()
    
    md_path = supervisor.export_reports()
    assert md_path.exists()
    
    content = md_path.read_text(encoding="utf-8")
    assert "# MBM GTM Agents & Bots Monitoring Report" in content
    assert "Neteller" in content
    assert "4599228811" in content
    
    json_path = ARTIFACTS_DIR / "gtm_agents_status.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["status"] == "HEALTHY"
    assert "system_health" in data


def test_gtm_master_runner_full_cycle():
    """Verify end-to-end execution of the GTM supervisor."""
    supervisor = GtmAgentSupervisor(run_mode="all")
    result = supervisor.run()
    
    assert result["status"] == "HEALTHY"
    assert "monitored_processes" in result
    assert "agents" in result
    assert "hunter" in result["agents"]
    assert "outreach" in result["agents"]
    assert "closer" in result["agents"]
    assert "creator" in result["agents"]
