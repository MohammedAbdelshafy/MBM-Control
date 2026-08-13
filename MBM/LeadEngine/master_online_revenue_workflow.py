"""
master_online_revenue_workflow.py — Master Automated Online Revenue Workflow
=============================================================================
Orchestrates the entire automated online money-making suite:
1. Upwork/B2B Freelance Bidding Daemon ($12,500 Pitch Pipeline)
2. High-Ticket DFY Offers & Distressed Real Estate Matcher ($250,000 Fee Pipeline)
3. B2B Audit-to-Close Engine ($5,995 Teardown Pipeline)
4. Shopify Storefront Catalog Sync (6 Flagship Products)
5. Whop Monetization Storefront Sync
6. Revenue Accountability Gate Audit
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

MASTER_SUMMARY_FILE = LOGS_DIR / "master_online_revenue_workflow_summary.json"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "Scripts"))

def run_master_online_revenue_workflow():
    print("#" * 70)
    print("  JARVIS OS — MASTER AUTOMATED ONLINE REVENUE WORKFLOW")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("#" * 70)
    
    workflow_results = {}
    
    # 1. Upwork Autonomous Bidding Daemon
    print("\n[STEP 1/6] Running Upwork B2B Contract Bidding Engine...")
    try:
        from upwork_auto_bidding_daemon import run_upwork_auto_binner
        upwork_bids = run_upwork_auto_binner()
        workflow_results["upwork_bidding"] = {
            "status": "SUCCESS",
            "bids_submitted": len(upwork_bids),
            "pipeline_value": 12500.00,
            "simulated": True,
        }
    except Exception as e:
        print(f"[-] Upwork bidding failed: {e}")
        workflow_results["upwork_bidding"] = {"status": "FAILED", "error": str(e)}

    # 2. High-Ticket Offers & Seller-Buyer Matcher
    print("\n[STEP 2/6] Running High-Ticket Revenue Engine & Deal Matcher...")
    try:
        from high_ticket_instant_monetizer import run_high_ticket_monetizer
        ht_report = run_high_ticket_monetizer()
        workflow_results["high_ticket_monetization"] = {
            "status": "SUCCESS",
            "matched_deals": ht_report.get("matched_deals_count", 0),
            "potential_assignment_revenue": ht_report.get("potential_assignment_revenue", 0.0)
        }
    except Exception as e:
        print(f"[-] High-ticket monetizer failed: {e}")
        workflow_results["high_ticket_monetization"] = {"status": "FAILED", "error": str(e)}

    # 2.5 CRM Blueprint Generation
    print("\n[STEP 2.5] Generating Agent-Ready CRM Blueprints...")
    try:
        import blueprint_generator
        bp_summary = blueprint_generator.run_blueprint_generation()
        workflow_results["crm_blueprints"] = {
            "status": "SUCCESS",
            "blueprints_generated": len(bp_summary.get("blueprints", []))
        }
    except Exception as e:
        print(f"[-] CRM Blueprint generator failed: {e}")
        workflow_results["crm_blueprints"] = {"status": "FAILED", "error": str(e)}

    # 2.7 Internal AAA Workflows
    print("\n[STEP 2.7] Running Internal AAA Workflows (Client Intake, Revenue Recovery, Content)...")
    try:
        import client_intake_agent
        import revenue_recovery_agent
        import content_repurposing_agent
        
        intake_res = client_intake_agent.run_intake_agent()
        recovery_res = revenue_recovery_agent.run_recovery_agent()
        content_res = content_repurposing_agent.run_content_agent()
        
        workflow_results["aaa_workflows"] = {
            "status": "SUCCESS",
            "intake_pipeline_value": intake_res.get("total_value", 0),
            "recovered_revenue": recovery_res.get("total_value_protected", 0),
            "content_assets_generated": sum(r["assets_generated"]["twitter_threads"] + r["assets_generated"]["linkedin_posts"] + r["assets_generated"]["facebook_updates"] for r in content_res.get("assets", []))
        }
    except Exception as e:
        print(f"[-] AAA Workflows failed: {e}")
        workflow_results["aaa_workflows"] = {"status": "FAILED", "error": str(e)}

    # 3. B2B Audit-to-Close Engine
    print("\n[STEP 3/6] Running B2B Audit-to-Close Pipeline...")
    try:
        from b2b_audit_engine import run_b2b_audit_pipeline
        audit_summary = run_b2b_audit_pipeline()
        workflow_results["b2b_audit_pipeline"] = {
            "status": "SUCCESS",
            "prospects_audited": audit_summary.get("total_prospects_audited", 0),
            "pipeline_value": audit_summary.get("total_audit_pipeline_value", 0.0)
        }
    except Exception as e:
        print(f"[-] B2B Audit pipeline failed: {e}")
        workflow_results["b2b_audit_pipeline"] = {"status": "FAILED", "error": str(e)}

    # 4. Shopify Storefront Sync
    print("\n[STEP 4/6] Syncing Shopify Storefront Catalog...")
    try:
        sys.path.insert(0, str(ROOT_DIR / "MBM" / "Shopify"))
        from shopify_storefront_engine import sync_catalog
        catalog = sync_catalog()
        workflow_results["shopify_storefront"] = {
            "status": "SUCCESS",
            "products_synced": len(catalog.get("products", []))
        }
    except Exception as e:
        print(f"[-] Shopify catalog sync failed: {e}")
        workflow_results["shopify_storefront"] = {"status": "FAILED", "error": str(e)}

    # 5. Whop Monetization Sync
    print("\n[STEP 5/6] Checking Whop Storefront Monetization Status...")
    try:
        sys.path.insert(0, str(ROOT_DIR / "MBM" / "Whop"))
        from whop_monetize import cmd_report
        whop_rep = cmd_report()
        workflow_results["whop_monetization"] = {
            "status": "SUCCESS",
            "products_active": len(whop_rep.get("products", []))
        }
    except Exception as e:
        print(f"[-] Whop report failed: {e}")
        workflow_results["whop_monetization"] = {"status": "FAILED", "error": str(e)}

    # 6. Hourly Revenue Accountability Gate Check
    print("\n[STEP 6/6] Executing Revenue Accountability Gate Audit...")
    try:
        from revenue_tracker import RevenueTracker
        tracker = RevenueTracker()
        gate_result = tracker.hourly_revenue_check()
        workflow_results["revenue_gate"] = {
            "status": "SUCCESS",
            "score": gate_result.get("score", 0),
            "made_money": gate_result.get("made_money", False),
            "escalation_level": gate_result.get("escalation_level", "NORMAL")
        }
    except Exception as e:
        print(f"[-] Revenue tracker gate failed: {e}")
        workflow_results["revenue_gate"] = {"status": "FAILED", "error": str(e)}

    # REAL MONEY vs POTENTIAL: the revenue gate counts confirmed paid
    # client_orders rows. Everything else in this workflow is pipeline
    # *potential* (opportunity value, bids, estimated fees) — never revenue.
    real_confirmed_revenue = 0.0
    try:
        from revenue_tracker import RevenueTracker
        real_confirmed_revenue = float(
            RevenueTracker().collect_signals().get("paid_orders", 0) or 0
        )
    except Exception as e:
        print(f"[-] Could not compute real confirmed revenue: {e}")

    potential_pipeline_value = (
        workflow_results.get("upwork_bidding", {}).get("pipeline_value", 0.0) +
        workflow_results.get("high_ticket_monetization", {}).get("potential_assignment_revenue", 0.0) +
        workflow_results.get("b2b_audit_pipeline", {}).get("pipeline_value", 0.0) +
        workflow_results.get("aaa_workflows", {}).get("intake_pipeline_value", 0.0) +
        workflow_results.get("aaa_workflows", {}).get("recovered_revenue", 0.0)
    )

    summary_doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Legacy key kept for consumers; clearly labeled POTENTIAL, not revenue.
        "total_active_pipeline_value": potential_pipeline_value,
        "potential_pipeline_value": potential_pipeline_value,
        # The only number that represents actual money in the bank/ledger.
        "real_confirmed_revenue_usd": real_confirmed_revenue,
        "workflow_results": workflow_results,
        "status": "MASTER_WORKFLOW_COMPLETE"
    }

    with open(MASTER_SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary_doc, f, indent=2, default=str)

    print("\n" + "#" * 70)
    print("  MASTER AUTOMATED ONLINE REVENUE WORKFLOW COMPLETE")
    print(f"  Real Confirmed Revenue: ${real_confirmed_revenue:,.2f}")
    print(f"  Pipeline Potential (not revenue): ${potential_pipeline_value:,.2f}")
    print(f"  Summary saved to: {MASTER_SUMMARY_FILE}")
    print("#" * 70)
    return summary_doc

if __name__ == "__main__":
    run_master_online_revenue_workflow()
