"""
Blueprint Generator (Agent-Ready CRM Workflows)
==============================================
Generates installable JSON blueprints for Make.com / n8n / GoHighLevel.
These blueprints connect our Data API directly to agency CRMs.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
BLUEPRINTS_DIR = BASE_DIR / "blueprints"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_make_blueprint():
    """Generates a Make.com JSON blueprint for Distressed Lead Ingestion."""
    blueprint = {
        "name": "MBM LeadEngine -> CRM (Missed Call Text Back & Distressed Leads)",
        "flow": [
            {
                "id": 1,
                "module": "http:ActionGetRest",
                "version": 3,
                "parameters": {
                    "url": "https://api.mbm-leadengine.com/api/v1/real-estate/distressed",
                    "method": "get",
                    "headers": [
                        {"name": "X-API-Key", "value": "{{apiKey}}"}
                    ]
                },
                "mapper": {}
            },
            {
                "id": 2,
                "module": "gohighlevel:ActionCreateContact",
                "version": 1,
                "parameters": {
                    "firstName": "{{1.data.contactName}}",
                    "phone": "{{1.data.phone}}",
                    "tags": ["MBM Distressed Lead", "{{1.data.motivation}}"]
                },
                "mapper": {}
            }
        ],
        "metadata": {
            "version": 1,
            "scenario": {
                "roundtrips": 1,
                "maxErrors": 3,
                "autoCommit": True
            }
        }
    }
    
    file_path = BLUEPRINTS_DIR / "make_distressed_lead_ingestion.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, indent=2)
    return str(file_path)

def generate_n8n_blueprint():
    """Generates an n8n JSON workflow blueprint for B2B Audit Intake."""
    blueprint = {
        "name": "MBM B2B Audit Pipeline -> Slack / CRM",
        "nodes": [
            {
                "parameters": {
                    "pollTimes": {"item": [{"mode": "everyMinute"}]}
                },
                "name": "Cron",
                "type": "n8n-nodes-base.cron",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": "https://api.mbm-leadengine.com/api/v1/b2b/audits",
                    "headerParameters": {
                        "parameters": [
                            {"name": "X-API-Key", "value": "={{$env.MBM_API_KEY}}"}
                        ]
                    }
                },
                "name": "Fetch B2B Audits",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [450, 300]
            }
        ],
        "connections": {
            "Cron": {
                "main": [
                    [{"node": "Fetch B2B Audits", "type": "main", "index": 0}]
                ]
            }
        }
    }
    
    file_path = BLUEPRINTS_DIR / "n8n_b2b_audit_pipeline.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, indent=2)
    return str(file_path)

def generate_aaa_intake_blueprint():
    blueprint = {"name": "AAA Client Intake & Proposal Generation"}
    file_path = BLUEPRINTS_DIR / "aaa_client_intake.json"
    with open(file_path, "w", encoding="utf-8") as f: json.dump(blueprint, f)
    return str(file_path)

def generate_aaa_recovery_blueprint():
    blueprint = {"name": "AAA Revenue Recovery Engine"}
    file_path = BLUEPRINTS_DIR / "aaa_revenue_recovery.json"
    with open(file_path, "w", encoding="utf-8") as f: json.dump(blueprint, f)
    return str(file_path)

def generate_aaa_content_blueprint():
    blueprint = {"name": "AAA Omnichannel Content Pipeline"}
    file_path = BLUEPRINTS_DIR / "aaa_content_repurposing.json"
    with open(file_path, "w", encoding="utf-8") as f: json.dump(blueprint, f)
    return str(file_path)

def run_blueprint_generation():
    print("=== GENERATING AUTOMATION BLUEPRINTS ===")
    make_file = generate_make_blueprint()
    n8n_file = generate_n8n_blueprint()
    aaa_intake = generate_aaa_intake_blueprint()
    aaa_recovery = generate_aaa_recovery_blueprint()
    aaa_content = generate_aaa_content_blueprint()
    
    print(f"[+] Make.com Blueprint generated: {make_file}")
    print(f"[+] n8n Blueprint generated: {n8n_file}")
    print(f"[+] AAA Intake Blueprint generated: {aaa_intake}")
    print(f"[+] AAA Recovery Blueprint generated: {aaa_recovery}")
    print(f"[+] AAA Content Blueprint generated: {aaa_content}")
    print("========================================")
    
    # Update Shopify Catalog array to include blueprints
    return {
        "status": "SUCCESS",
        "blueprints": [make_file, n8n_file]
    }

if __name__ == "__main__":
    run_blueprint_generation()
