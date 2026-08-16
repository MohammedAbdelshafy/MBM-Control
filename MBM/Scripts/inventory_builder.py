#!/usr/bin/env python3
"""
MBM Ecosystem Comprehensive Repository & Subsystem Inventory Builder
Generates GLM_REPO_INVENTORY.json and GLM_REPO_INVENTORY.md
"""

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Any

ROOT = Path(__file__).resolve().parent.parent.parent

def run_cmd(args: List[str], cwd: Path) -> str:
    try:
        res = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=10)
        return res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
    except Exception as e:
        return f"Error: {e}"

def get_git_info(repo_path: Path) -> Dict[str, Any]:
    if not (repo_path / ".git").exists():
        return {
            "is_git_repo": False,
            "status": "Nested Subsystem / Module",
            "remote": "Parent Monorepo",
            "branch": "master",
            "latest_commit": "Tracked in parent",
            "dirty_files": [],
            "recent_commits": [],
        }
    
    remote = run_cmd(["git", "remote", "-v"], repo_path)
    branch = run_cmd(["git", "branch", "--show-current"], repo_path)
    branch_vv = run_cmd(["git", "branch", "-vv"], repo_path)
    status_short = run_cmd(["git", "status", "--short"], repo_path)
    log_10 = run_cmd(["git", "log", "-10", "--oneline"], repo_path)
    
    dirty = [line.strip() for line in status_short.splitlines() if line.strip()]
    commits = [line.strip() for line in log_10.splitlines() if line.strip()]
    
    return {
        "is_git_repo": True,
        "remote": remote,
        "branch": branch or "HEAD",
        "branch_verbose": branch_vv,
        "latest_commit": commits[0] if commits else "N/A",
        "dirty_files": dirty[:30],
        "dirty_count": len(dirty),
        "recent_commits": commits[:10],
    }

def audit_ecosystem() -> List[Dict[str, Any]]:
    repos_spec = [
        {
            "repo": "Base44 Control Plane (Root Monorepo)",
            "path": ".",
            "tech_stack": "React 18 + Vite 6 + Tailwind CSS + FastAPI + Node/Express + Celery + Python 3.11",
            "entrypoints": [
                "src/main.jsx",
                "server/index.js",
                "MBM/LeadEngine/gemini_agent_api.py",
                "clipping-factory/main.py",
            ],
            "tests": "pytest MBM/LeadEngine/tests/ -v (204 tests passing), npm run test",
            "deployment": "Vite dev (:5173), Express (:3002), FastAPI (:3005), Docker Compose stack",
            "dependencies": "package.json (React/Vite), requirements.txt, pyproject.toml",
            "known_blockers": "Auction.com scrape blocked by Incapsula; RapidAPI 429 rate limit observed",
            "revenue_role": "Core Operating Platform, GTM Engine, Monorepo Orchestration",
            "risk_level": "CRITICAL",
        },
        {
            "repo": "MBM Dialer (Tonight Caller Cockpit)",
            "path": "mbm-dialer",
            "tech_stack": "TanStack Start / Router + React 18 + Tailwind CSS + Bun / Vite",
            "entrypoints": [
                "mbm-dialer/app/src/routes/index.tsx",
                "mbm-dialer/app/src/components/dialer/MasterScript.tsx",
                "mbm-dialer/app/src/router.tsx",
            ],
            "tests": "tsc --noEmit (0 errors), bun run build",
            "deployment": "Bun/Vite runtime (:5173), Proxy to FastAPI (:3005)",
            "dependencies": "mbm-dialer/app/package.json (@tanstack/react-router, tailwindcss)",
            "known_blockers": "Historical 762 -> 702 data rewrite race (Resolved with Single-Writer Lock rule)",
            "revenue_role": "Primary Calling & Closing Interface (Sellers + AI Consultancy)",
            "risk_level": "CRITICAL",
        },
        {
            "repo": "MBM-Social (Multi-Brand Media & Content OS)",
            "path": "MBM-Social",
            "tech_stack": "Python 3.11 + Pydantic + SQLite + Docker + ComfyUI + Playwright",
            "entrypoints": [
                "MBM-Social/mbm.py",
                "MBM-Social/Operations/campaign_runtime.py",
                "MBM-Social/Operations/oauth_manager.py",
                "MBM-Social/Factories/PublishFactory/publish_worker.py",
            ],
            "tests": "pytest MBM-Social/tests/",
            "deployment": "Docker Compose (ComfyUI + Workers + Telegram Daemon)",
            "dependencies": "MBM-Social/requirements.txt (playwright, yt-dlp, pydantic, groq)",
            "known_blockers": "YouTube OAuth interactive flow requires browser auth on first run",
            "revenue_role": "Top-of-Funnel Content Ingestion, Engagement & Business Signal Discovery",
            "risk_level": "HIGH",
        },
        {
            "repo": "MBM LeadEngine (GTM Intelligence & Discovery)",
            "path": "MBM/LeadEngine",
            "tech_stack": "Python 3.11 + FastAPI + Pydantic v2 + SQLite + Groq LPU + Gemini 2.5 + NVIDIA NIM",
            "entrypoints": [
                "MBM/LeadEngine/gemini_agent_api.py",
                "MBM/LeadEngine/daily_fresh_lead_factory.py",
                "MBM/LeadEngine/gtm_commander.py",
                "MBM/LeadEngine/gtm_notification_bus.py",
                "MBM/LeadEngine/conversation_engine.py",
            ],
            "tests": "pytest MBM/LeadEngine/tests/ -v (204 tests passing)",
            "deployment": "FastAPI daemon on port 3005, CLI daemons, Scheduled Cron",
            "dependencies": "requirements.txt (fastapi, uvicorn, groq, google-genai)",
            "known_blockers": "Twilio Lookup 401 (Replaced by Free CMS NPI & DCAD Verified records)",
            "revenue_role": "100+ Daily Fresh Verified Leads, GTM Attribution, Discovery, Meeting Booking",
            "risk_level": "CRITICAL",
        },
        {
            "repo": "Clipping Factory (Autonomous Video Engine)",
            "path": "clipping-factory",
            "tech_stack": "Python / FastAPI + Celery + Redis + Docker + PostgreSQL + MinIO",
            "entrypoints": [
                "clipping-factory/main.py",
                "clipping-factory/tasks.py",
                "clipping-factory/worker.py",
            ],
            "tests": "pytest clipping-factory/tests/",
            "deployment": "12-Container Docker Compose Stack (API, workers, beat, Redis, MinIO)",
            "dependencies": "clipping-factory/requirements.txt, Dockerfile",
            "known_blockers": "Local GPU rendering requires CUDA/NVIDIA container toolkit",
            "revenue_role": "Automated Short-Form & Video Asset Production Engine",
            "risk_level": "MEDIUM",
        },
        {
            "repo": "MBM Ops & Real Estate Underwriting",
            "path": "MBM",
            "tech_stack": "Python 3.11 + RapidAPI + Neteller API + Pandas",
            "entrypoints": [
                "MBM/LeadEngine/property_intel/ownership_verifier.py",
                "MBM/LeadEngine/seller_skip_tracer.py",
                "MBM/Scripts/neteller_config.py",
            ],
            "tests": "pytest MBM/LeadEngine/tests/test_property_intel.py",
            "deployment": "Python CLI scripts, Scheduled cron workflows",
            "dependencies": "Python standard library + requests + beautifulsoup4",
            "known_blockers": "County ArcGIS endpoints can have variable latency",
            "revenue_role": "Wholesale Deal Assignment, Property Dossiers, Cash Offer Underwriting",
            "risk_level": "HIGH",
        },
        {
            "repo": "ConTech BOQ & CAD Estimator Subsystem",
            "path": "MBM-Social/ContechAI",
            "tech_stack": "Python 3.11 + DXF parser + Eurocode / MasterFormat Cost Matrix",
            "entrypoints": [
                "MBM-Social/ContechAI/boq_engine.py",
                "MBM-Social/ContechAI/cad_parser.py",
            ],
            "tests": "pytest MBM-Social/tests/test_contech.py",
            "deployment": "CLI tool & FastAPI endpoint",
            "dependencies": "ezdxf, numpy, pydantic",
            "known_blockers": "Scanned PDF takeoffs require vectorization OCR",
            "revenue_role": "High-Ticket Construction AI Retainers & CAD-to-BOQ Automation ($2,497/mo)",
            "risk_level": "MEDIUM",
        },
    ]

    results = []
    for spec in repos_spec:
        p = ROOT / spec["path"]
        git_info = get_git_info(p)
        item = {**spec, **git_info, "path_abs": str(p.resolve())}
        results.append(item)
    
    return results

def main():
    print("Building MBM Ecosystem GLM Repository & Subsystem Inventory...")
    inventory = audit_ecosystem()
    
    artifacts_dir = ROOT / "MBM" / "Artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = artifacts_dir / "GLM_REPO_INVENTORY.json"
    md_path = artifacts_dir / "GLM_REPO_INVENTORY.md"
    
    # Write JSON
    json_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote JSON inventory: {json_path}")
    
    # Write Markdown
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_lines = [
        "# 🌐 MBM Ecosystem — GLM Repository & Subsystem Inventory",
        f"**Generated:** {now_str}  ",
        f"**Total Tracked Repositories / Subsystems:** {len(inventory)}  ",
        "",
        "---",
        "",
        "## 📊 Executive Subsystem Matrix",
        "",
        "| Subsystem / Repository | Path | Git Branch | Tech Stack | Risk Level | Revenue Role |",
        "|---|---|---|---|---|---|",
    ]
    
    for item in inventory:
        branch_name = item.get("branch") or "master"
        md_lines.append(
            f"| **{item['repo']}** | `{item['path']}` | `{branch_name}` | {item['tech_stack'].split('+')[0].strip()} | `{item['risk_level']}` | {item['revenue_role']} |"
        )
    
    md_lines.extend([
        "",
        "---",
        "",
        "## 🔍 Detailed Subsystem Dossiers",
        "",
    ])
    
    for item in inventory:
        md_lines.extend([
            f"### 📦 {item['repo']}",
            f"- **Path:** `{item['path']}` (`{item['path_abs']}`)",
            f"- **Is Git Repo:** `{'Yes' if item['is_git_repo'] else 'Nested Subsystem'}`",
            f"- **Branch:** `{item['branch']}`",
            f"- **Latest Commit:** `{item['latest_commit']}`",
            f"- **Tech Stack:** {item['tech_stack']}",
            f"- **Entrypoints:**",
        ])
        for ep in item["entrypoints"]:
            md_lines.append(f"  - `{ep}`")
        md_lines.extend([
            f"- **Test Suite:** {item['tests']}",
            f"- **Deployment:** {item['deployment']}",
            f"- **Dependencies:** {item['dependencies']}",
            f"- **Known Blockers:** {item['known_blockers']}",
            f"- **Revenue Role:** {item['revenue_role']}",
            f"- **Risk Level:** `{item['risk_level']}`",
            f"- **Dirty Files Count:** {item.get('dirty_count', len(item.get('dirty_files', [])))}",
            "",
        ])
        if item.get("recent_commits"):
            md_lines.append("  **Recent Commits:**")
            for c in item["recent_commits"][:5]:
                md_lines.append(f"  - `{c}`")
            md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote Markdown inventory: {md_path}")

if __name__ == "__main__":
    main()
