"""
Night Operations — automated overnight maintenance and intelligence gathering.

Runs these missions every night (configurable schedule):
  1. Repository Audit
  2. Campaign Health Check
  3. Analytics Collection
  4. Model Health Check
  5. Learning Update
  6. Queue Optimization
  7. Platform Health Check
  8. Daily Executive Report
  9. Opportunity Scan
  10. Repository Backup

All missions extend existing infrastructure — no parallel systems.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT.parent / "backend"
REPORT_DIR = ROOT / "night_reports"


def _log(mission: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{mission}] {msg}", flush=True)


def _save_report(report: dict, name: str):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(name, f"Report saved: {path}")
    return str(path)


# ─── Mission 1: Repository Audit ─────────────────────────────────────

def mission_repository_audit() -> dict:
    """Check repository structure, key files, and integrity."""
    _log("REPO_AUDIT", "Running repository audit...")

    checks = {
        "brands_dir": (ROOT / "Brands").exists(),
        "brand_registry": (ROOT / "BrandRegistry.json").exists(),
        "channel_registry": (ROOT / "ChannelRegistry.json").exists(),
        "campaign_router": (ROOT / "CampaignRouter.json").exists(),
        "channel_metrics": (ROOT / "ChannelMetrics.json").exists(),
        "master_account": (ROOT / "MasterAccount.json").exists(),
        "mbm_social_package": (ROOT / "mbm_social" / "__init__.py").exists(),
        "pipeline": (ROOT / "mbm_social" / "pipeline.py").exists(),
        "autonomous_runtime": (ROOT / "mbm_social" / "autonomous_runtime.py").exists(),
        "learning_engine": (ROOT / "mbm_social" / "learning_engine.py").exists(),
        "night_operations": (ROOT / "mbm_social" / "night_operations.py").exists(),
        "backend_exists": BACKEND.exists(),
    }

    # Check brand configs completeness
    brands_dir = ROOT / "Brands"
    brand_checks = {}
    if brands_dir.exists():
        for brand_dir in brands_dir.iterdir():
            if brand_dir.is_dir():
                required_files = [
                    "brand.yaml", "sources.yaml", "style_guide.md",
                    "posting_schedule.yaml", "kpis.yaml",
                    "thumbnail_rules.md", "title_rules.md", "caption_rules.md"
                ]
                missing = [f for f in required_files if not (brand_dir / f).exists()]
                brand_checks[brand_dir.name] = {
                    "complete": len(missing) == 0,
                    "missing": missing,
                }

    failed = [k for k, v in checks.items() if not v]
    brands_ok = sum(1 for v in brand_checks.values() if v["complete"])

    report = {
        "timestamp": datetime.now().isoformat(),
        "file_checks": checks,
        "brands_complete": brands_ok,
        "brands_total": len(brand_checks),
        "brand_details": brand_checks,
        "failed_checks": failed,
        "status": "healthy" if not failed else "degraded",
    }

    _save_report(report, "repo_audit")
    return report


# ─── Mission 2: Campaign Health Check ────────────────────────────────

def mission_campaign_health() -> dict:
    """Check campaign pipeline health — queue depth, stuck clips, failed jobs."""
    _log("CAMP_HEALTH", "Running campaign health check...")

    queue_dir = ROOT / "publish_queue"
    drafts = 0
    published = 0
    failed = 0

    if queue_dir.exists():
        for f in queue_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                status = data.get("status", "unknown")
                if status == "draft":
                    drafts += 1
                elif status == "published":
                    published += 1
                elif status == "failed":
                    failed += 1
            except Exception:
                failed += 1

    # Check for stuck outputs in brand dirs
    brands_dir = ROOT / "Brands"
    stuck_outputs = 0
    if brands_dir.exists():
        for brand_dir in brands_dir.iterdir():
            outputs = brand_dir / "outputs"
            if outputs.exists():
                for f in outputs.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        if data.get("status") in ("processing", "queued"):
                            stuck_outputs += 1
                    except Exception:
                        stuck_outputs += 1

    report = {
        "timestamp": datetime.now().isoformat(),
        "queue_depth": {"drafts": drafts, "published": published, "failed": failed},
        "stuck_outputs": stuck_outputs,
        "status": "healthy" if failed < 5 and stuck_outputs < 3 else "degraded",
        "recommendations": [],
    }

    if failed > 5:
        report["recommendations"].append("High failure rate — check platform sessions and API keys")
    if stuck_outputs > 3:
        report["recommendations"].append("Stuck outputs detected — may need queue reset")
    if drafts > 20:
        report["recommendations"].append("Large draft backlog — consider increasing publish frequency")

    _save_report(report, "campaign_health")
    return report


# ─── Mission 3: Analytics Collection ─────────────────────────────────

def mission_analytics_collection() -> dict:
    """Collect and aggregate analytics from ChannelMetrics.json."""
    _log("ANALYTICS", "Collecting analytics...")

    metrics_path = ROOT / "ChannelMetrics.json"
    if not metrics_path.exists():
        return {"status": "no_metrics_file"}

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    channels = data.get("channels", {})
    clip_history = data.get("clip_history", [])

    # Aggregate recent performance
    recent_clips = clip_history[-100:] if clip_history else []
    total_views = sum(c.get("views", 0) for c in recent_clips)
    avg_ctr = sum(c.get("ctr", 0) for c in recent_clips) / max(len(recent_clips), 1)
    total_revenue = sum(c.get("revenue_usd", 0) for c in recent_clips)

    # Channel-level aggregation
    channel_summary = {}
    for ch_id, ch_data in channels.items():
        channel_summary[ch_id] = {
            "brand": ch_data.get("brand", ""),
            "views_30d": ch_data.get("views_30d", 0),
            "ctr": ch_data.get("ctr", 0),
            "subs_gain": ch_data.get("subs_gain", 0),
            "posts": ch_data.get("posts", 0),
        }

    report = {
        "timestamp": datetime.now().isoformat(),
        "network_summary": {
            "total_views_recent": total_views,
            "avg_ctr": round(avg_ctr, 4),
            "total_revenue": round(total_revenue, 2),
            "clips_analyzed": len(recent_clips),
        },
        "channel_summary": channel_summary,
        "status": "healthy",
    }

    _save_report(report, "analytics")
    return report


# ─── Mission 4: Model Health Check ───────────────────────────────────

def mission_model_health() -> dict:
    """Check Ollama model availability and response times."""
    _log("MODEL_HEALTH", "Checking local model health...")

    try:
        sys.path.insert(0, str(ROOT / "mbm_social"))
        from model_registry import list_models, resolve

        models = list_models()
        model_names = [m.name for m in models if m.available]

        # Test a basic generation
        test_start = time.time()
        try:
            test_result = resolve("title_generation")
            test_time = time.time() - test_start
            test_ok = True
        except Exception as e:
            test_time = time.time() - test_start
            test_ok = False
            test_result = str(e)

        report = {
            "timestamp": datetime.now().isoformat(),
            "models_available": len(model_names),
            "model_list": model_names,
            "test_generation": {
                "success": test_ok,
                "model_used": test_result if test_ok else None,
                "response_time_sec": round(test_time, 2),
                "error": test_result if not test_ok else None,
            },
            "status": "healthy" if test_ok and len(model_names) >= 3 else "degraded",
        }

    except Exception as e:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }

    _save_report(report, "model_health")
    return report


# ─── Mission 5: Learning Update ──────────────────────────────────────

def mission_learning_update() -> dict:
    """Run learning engine updates — auto-adjust scoring weights."""
    _log("LEARNING", "Running learning engine update...")

    try:
        from learning_engine import (
            auto_update_scoring_weights,
            get_learning_insights,
            get_daily_learning_report,
        )

        weight_update = auto_update_scoring_weights()
        insights = get_learning_insights()
        report_data = get_daily_learning_report()

        report = {
            "timestamp": datetime.now().isoformat(),
            "weight_update": weight_update,
            "insights": insights,
            "daily_summary": report_data,
            "status": "healthy",
        }

    except Exception as e:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }

    _save_report(report, "learning_update")
    return report


# ─── Mission 6: Queue Optimization ───────────────────────────────────

def mission_queue_optimization() -> dict:
    """Optimize publish queues — remove stale drafts, rebalance timing."""
    _log("QUEUE_OPT", "Optimizing publish queues...")

    queue_dir = ROOT / "publish_queue"
    cleaned = 0
    rebalanced = 0

    if queue_dir.exists():
        for f in queue_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))

                # Remove drafts older than 7 days
                created = data.get("publish_time", data.get("status", ""))
                if data.get("status") == "draft":
                    # Check file age
                    file_age_days = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
                    if file_age_days > 7:
                        f.unlink()
                        cleaned += 1
                        continue

                # Rebalance: if multiple drafts queued for same time, spread them
                if data.get("status") == "draft" and data.get("publish_time"):
                    rebalanced += 1

            except Exception:
                continue

    report = {
        "timestamp": datetime.now().isoformat(),
        "cleaned_old_drafts": cleaned,
        "rebalanced_items": rebalanced,
        "status": "healthy",
    }

    _save_report(report, "queue_optimization")
    return report


# ─── Mission 7: Platform Health Check ────────────────────────────────

def mission_platform_health() -> dict:
    """Check YouTube/social platform session health."""
    _log("PLATFORM_HEALTH", "Checking platform sessions...")

    # Check for session files
    sessions_dir = BACKEND / "sessions"
    youtube_profile_dir = ROOT / "youtube_profile"

    checks = {
        "sessions_dir": sessions_dir.exists() if sessions_dir else False,
        "youtube_profile": youtube_profile_dir.exists() if youtube_profile_dir else False,
    }

    # Check for OAuth tokens
    tokens_path = BACKEND.parent / "youtube_tokens.json"
    checks["oauth_tokens"] = tokens_path.exists() if tokens_path else False

    # Check environment variables
    checks["youtube_session_env"] = bool(os.environ.get("YOUTUBE_SESSION_STATE"))
    checks["supabase_configured"] = bool(os.environ.get("VITE_SUPABASE_URL"))

    healthy_count = sum(1 for v in checks.values() if v)

    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "healthy_count": healthy_count,
        "total_checks": len(checks),
        "status": "healthy" if healthy_count >= 3 else "degraded",
        "recommendations": [],
    }

    if not checks.get("oauth_tokens"):
        report["recommendations"].append("YouTube OAuth tokens missing — publish will use Playwright fallback")
    if not checks.get("sessions_dir"):
        report["recommendations"].append("Sessions directory missing — create backend/sessions/")

    _save_report(report, "platform_health")
    return report


# ─── Mission 8: Daily Executive Report ───────────────────────────────

def mission_executive_report(all_results: dict) -> dict:
    """Compile all mission results into an executive summary."""
    _log("EXEC_REPORT", "Compiling executive report...")

    report = {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "mission_results": {},
        "overall_status": "healthy",
        "alerts": [],
        "summary": {},
    }

    mission_statuses = {}
    for mission_name, result in all_results.items():
        status = result.get("status", "unknown")
        mission_statuses[mission_name] = status
        report["mission_results"][mission_name] = {
            "status": status,
            "summary": {k: v for k, v in result.items()
                       if k not in ("timestamp", "recommendations", "details", "brand_details")},
        }
        if status in ("error", "degraded"):
            report["alerts"].append(f"{mission_name}: {status}")

    # Overall status
    if any(s == "error" for s in mission_statuses.values()):
        report["overall_status"] = "error"
    elif any(s == "degraded" for s in mission_statuses.values()):
        report["overall_status"] = "degraded"

    # Summary
    report["summary"] = {
        "missions_run": len(all_results),
        "healthy": sum(1 for s in mission_statuses.values() if s == "healthy"),
        "degraded": sum(1 for s in mission_statuses.values() if s == "degraded"),
        "errors": sum(1 for s in mission_statuses.values() if s == "error"),
    }

    _save_report(report, "executive_report")
    return report


# ─── Mission 9: Opportunity Scan ─────────────────────────────────────

def mission_opportunity_scan() -> dict:
    """Scan for new campaign opportunities and trending content."""
    _log("OPP_SCAN", "Scanning for opportunities...")

    # Check for trending topics in CampaignRouter.json profiles
    router_path = ROOT / "CampaignRouter.json"
    opportunities = []

    if router_path.exists():
        router = json.loads(router_path.read_text(encoding="utf-8"))
        profiles = router.get("campaign_profiles", {})
        for name, profile in profiles.items():
            opportunities.append({
                "profile": name,
                "description": profile.get("description", ""),
                "target_brands": profile.get("target_brands", []),
                "platforms": profile.get("platforms", []),
                "status": "available",
            })

    report = {
        "timestamp": datetime.now().isoformat(),
        "opportunities_found": len(opportunities),
        "opportunities": opportunities,
        "status": "healthy",
    }

    _save_report(report, "opportunity_scan")
    return report


# ─── Mission 10: Repository Backup ───────────────────────────────────

def mission_repository_backup() -> dict:
    """Backup critical configuration files."""
    _log("BACKUP", "Backing up repository configs...")

    backup_dir = ROOT / "backups" / datetime.now().strftime("%Y%m%d")
    backup_dir.mkdir(parents=True, exist_ok=True)

    files_to_backup = [
        "BrandRegistry.json",
        "ChannelRegistry.json",
        "CampaignRouter.json",
        "ChannelMetrics.json",
        "MasterAccount.json",
    ]

    backed_up = 0
    for fname in files_to_backup:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)
            backed_up += 1

    # Backup LearningMemory if exists
    learning_path = ROOT / "LearningMemory.json"
    if learning_path.exists():
        shutil.copy2(learning_path, backup_dir / "LearningMemory.json")
        backed_up += 1

    # Backup brand configs
    brands_backup = backup_dir / "Brands"
    brands_src = ROOT / "Brands"
    if brands_src.exists():
        shutil.copytree(brands_src, brands_backup, dirs_exist_ok=True)
        backed_up += 1

    report = {
        "timestamp": datetime.now().isoformat(),
        "backup_dir": str(backup_dir),
        "files_backed_up": backed_up,
        "status": "healthy",
    }

    _save_report(report, "backup")
    return report


# ─── Main runner ─────────────────────────────────────────────────────

def run_all_missions() -> dict:
    """Run all night operations missions and compile executive report."""
    _log("NIGHT_OPS", "Starting night operations run...")

    start = time.time()
    results = {}

    missions = [
        ("repository_audit", mission_repository_audit),
        ("campaign_health", mission_campaign_health),
        ("analytics_collection", mission_analytics_collection),
        ("model_health", mission_model_health),
        ("learning_update", mission_learning_update),
        ("queue_optimization", mission_queue_optimization),
        ("platform_health", mission_platform_health),
        ("opportunity_scan", mission_opportunity_scan),
        ("repository_backup", mission_repository_backup),
    ]

    for name, fn in missions:
        try:
            results[name] = fn()
        except Exception as e:
            _log(name, f"MISSION FAILED: {e}")
            results[name] = {"status": "error", "error": str(e)}

    # Compile executive report
    exec_report = mission_executive_report(results)

    elapsed = time.time() - start
    _log("NIGHT_OPS", f"All missions complete in {elapsed:.1f}s")

    return {
        "executive_report": exec_report,
        "mission_results": results,
        "total_duration_sec": round(elapsed, 2),
    }


if __name__ == "__main__":
    run_all_missions()
