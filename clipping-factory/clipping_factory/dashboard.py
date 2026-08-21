"""
Campaign Dashboard — generates a status report showing all campaigns
across all brands with their pipeline state.

Shows:
  DISCOVERED | RESEARCHED | SCRIPTED | IN_PRODUCTION | QA |
  READY_TO_PUBLISH | PUBLISHED | VERIFIED | REJECTED | FAILED
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


STATUS_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / "movie_status.json"
HEARTBEAT_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / "heartbeat.json"
DASHBOARD_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / "dashboard.md"


BRANDS = [
    "twistsrevealed",
    "cutedosage",
    "dontwatchthis",
    "goalmachinez",
    "clippingfactorymbm",
]


def load_status() -> Dict[str, Any]:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_heartbeat() -> Dict[str, Any]:
    if HEARTBEAT_FILE.exists():
        try:
            return json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "unknown"}


def generate_dashboard() -> str:
    """Generate a markdown dashboard of all campaigns."""
    status = load_status()
    hb = load_heartbeat()
    now = datetime.now(timezone.utc).isoformat()

    # Count by status
    status_counts: Dict[str, int] = {}
    brand_counts: Dict[str, Dict[str, int]] = {b: {} for b in BRANDS}

    for cid, entry in status.items():
        if not isinstance(entry, dict):
            continue
        s = entry.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

        title = entry.get("title", "")
        # Detect brand from campaign_id prefix
        brand = "twistsrevealed"  # Default for TR- prefixed
        if cid.startswith("CD-"):
            brand = "cutedosage"
        elif cid.startswith("DWT-"):
            brand = "dontwatchthis"
        elif cid.startswith("GM-"):
            brand = "goalmachinez"
        elif cid.startswith("CF-"):
            brand = "clippingfactorymbm"

        if brand not in brand_counts:
            brand_counts[brand] = {}
        brand_counts[brand][s] = brand_counts[brand].get(s, 0) + 1

    # Health color
    hb_status = hb.get("status", "unknown")
    if hb_status == "success":
        health_color = "GREEN"
    elif hb_status in ("running", "skipped_already_running"):
        health_color = "YELLOW"
    elif hb_status in ("failed", "no_heartbeat"):
        health_color = "RED"
    else:
        health_color = "YELLOW"

    # Build dashboard
    lines = []
    lines.append("# CLIPPING FACTORY DASHBOARD")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## FACTORY STATUS")
    lines.append("")
    lines.append(f"**Health: {health_color}**")
    lines.append(f"- Last status: `{hb_status}`")
    lines.append(f"- Last completed: `{hb.get('last_completed', 'never')}`")
    lines.append(f"- Duration: `{hb.get('duration_sec', 'N/A')}s`")
    lines.append("")

    lines.append("## CAMPAIGN PIPELINE")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for s in ["discovered", "researched", "scripted", "in_production", "qa", "ready_to_publish", "published", "verified", "rejected", "failed", "unknown"]:
        count = status_counts.get(s, 0)
        if count > 0:
            lines.append(f"| {s.upper().replace('_', ' ')} | {count} |")
    lines.append(f"| **TOTAL** | **{sum(status_counts.values())}** |")
    lines.append("")

    lines.append("## BRAND BREAKDOWN")
    lines.append("")
    for brand in BRANDS:
        bc = brand_counts.get(brand, {})
        total = sum(bc.values())
        lines.append(f"### {brand.upper()}")
        if total == 0:
            lines.append("- No campaigns")
        else:
            for s, c in sorted(bc.items()):
                lines.append(f"- {s}: {c}")
        lines.append("")

    lines.append("## CHANNEL PROFILES")
    lines.append("")
    for brand in BRANDS:
        lines.append(f"- **{brand}**: configured")
    lines.append("")

    lines.append("## RECENT CAMPAIGNS")
    lines.append("")
    recent = sorted(status.items(), key=lambda x: x[1].get("updated_at", ""), reverse=True)[:10]
    for cid, entry in recent:
        if isinstance(entry, dict):
            lines.append(f"- `{cid}` — {entry.get('title', 'N/A')} [{entry.get('status', 'unknown')}]")
    lines.append("")

    lines.append("## NEXT ACTIONS")
    lines.append("")
    if status_counts.get("discovered", 0) > 0:
        lines.append(f"- {status_counts['discovered']} campaigns need research")
    if status_counts.get("scripted", 0) > 0:
        lines.append(f"- {status_counts['scripted']} campaigns ready for production")
    if status_counts.get("ready_to_publish", 0) > 0:
        lines.append(f"- {status_counts['ready_to_publish']} clips ready to publish")
    if not status:
        lines.append("- No campaigns yet. Run movie discovery first.")
    lines.append("")

    dashboard = "\n".join(lines)

    # Write to file
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(dashboard, encoding="utf-8")

    return dashboard


if __name__ == "__main__":
    print(generate_dashboard())
