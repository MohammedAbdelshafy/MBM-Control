"""
MBM LeadEngine — Content Attribution Engine
=============================================
Tracks the full chain: content asset → campaign → source → CTA → lead → opportunity → revenue.
Avoids double attribution. Keeps attribution explainable.
All links are event-derived from audit_log_entries and revenue_events.
"""

from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from MBM.LeadEngine.ad_repository import AdRepository

log = logging.getLogger(__name__)


class ContentAttributionEngine:
    """
    Attribution engine that tracks content → lead → deal → revenue.
    Uses first-touch and last-touch models. Prevents double attribution
    by tracking the full attribution path on each revenue event.
    """

    def __init__(self, repo: Optional[AdRepository] = None):
        self.repo = repo or AdRepository()

    # ─── ATTRIBUTION RECORDING ────────────────────────────────────

    def record_content_touch(self, content_id: str, campaign_id: str,
                             lead_id: str, touch_type: str = "first_touch",
                             platform: str = "", metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Record a content touchpoint. Called when content generates a lead interaction.
        touch_type: "first_touch" | "assist" | "last_touch"
        """
        event = self.repo.log_event(
            event_type="content_touch",
            entity_id=lead_id,
            entity_type="lead",
            payload={
                "content_id": content_id,
                "campaign_id": campaign_id,
                "touch_type": touch_type,
                "platform": platform,
                **(metadata or {}),
            },
        )
        return event

    def attribute_lead_to_content(self, lead_id: str) -> Dict[str, Any]:
        """
        Resolve the full attribution chain for a lead.
        Returns first_touch, last_touch, and assist chain.
        """
        # Get all content_touch events for this lead
        # Since we don't have a direct query by entity_id in audit_log,
        # we use the audit entries from the repo
        all_events = []
        try:
            if self.repo._use_supabase():
                result = self.repo.client.table("audit_log_entries").select("*").eq(
                    "entity_id", lead_id
                ).eq("event_type", "content_touch").execute()
                all_events = result.data or []
            else:
                # For JSON fallback, scan audit log file
                from pathlib import Path
                audit_file = self.repo.storage_dir / "audit_log_entries.json"
                if audit_file.exists():
                    import json
                    entries = json.loads(audit_file.read_text(encoding="utf-8"))
                    all_events = [
                        e for e in entries
                        if e.get("entity_id") == lead_id
                        and e.get("event_type") == "content_touch"
                    ]
        except Exception as e:
            log.warning("Failed to query attribution for lead %s: %s", lead_id, e)

        first_touch = None
        last_touch = None
        assists = []

        for event in sorted(all_events, key=lambda x: x.get("created_at", "")):
            payload = event.get("payload", {})
            touch = {
                "content_id": payload.get("content_id", ""),
                "campaign_id": payload.get("campaign_id", ""),
                "platform": payload.get("platform", ""),
                "timestamp": event.get("created_at", ""),
            }
            touch_type = payload.get("touch_type", "assist")
            if touch_type == "first_touch" and first_touch is None:
                first_touch = touch
            elif touch_type == "last_touch":
                last_touch = touch
            else:
                assists.append(touch)

        # If no explicit first_touch, use earliest event
        if first_touch is None and all_events:
            earliest = all_events[0]
            payload = earliest.get("payload", {})
            first_touch = {
                "content_id": payload.get("content_id", ""),
                "campaign_id": payload.get("campaign_id", ""),
                "platform": payload.get("platform", ""),
                "timestamp": earliest.get("created_at", ""),
            }

        # If no explicit last_touch, use latest event
        if last_touch is None and all_events:
            latest = all_events[-1]
            payload = latest.get("payload", {})
            last_touch = {
                "content_id": payload.get("content_id", ""),
                "campaign_id": payload.get("campaign_id", ""),
                "platform": payload.get("platform", ""),
                "timestamp": latest.get("created_at", ""),
            }

        return {
            "lead_id": lead_id,
            "first_touch": first_touch,
            "last_touch": last_touch,
            "assists": assists,
            "total_touches": len(all_events),
        }

    # ─── REVENUE ATTRIBUTION ──────────────────────────────────────

    def attribute_revenue_to_content(self, deal_id: str) -> Dict[str, Any]:
        """
        Attribute a closed deal's revenue to content.
        Uses the attribution_path stored on revenue_events.
        Prevents double-counting by checking existing attribution.
        """
        events = self.repo.get_revenue_events({"deal_id": deal_id})
        if not events:
            return {"deal_id": deal_id, "attributed": False, "reason": "no_revenue_events"}

        revenue_event = events[0]
        attribution_path = revenue_event.get("attribution_path", [])

        # Check if already attributed (prevent double-counting)
        existing_content = revenue_event.get("content_id", "")
        if existing_content:
            return {
                "deal_id": deal_id,
                "attributed": True,
                "content_id": existing_content,
                "campaign_id": revenue_event.get("campaign_id", ""),
                "revenue": revenue_event.get("net_amount", 0),
                "model": revenue_event.get("attribution_model", "LAST_TOUCH"),
                "path": attribution_path,
                "note": "already_attributed",
            }

        # Attribute using first-touch from attribution path
        if attribution_path:
            first_content = attribution_path[0] if attribution_path else ""
            return {
                "deal_id": deal_id,
                "attributed": True,
                "content_id": first_content,
                "campaign_id": revenue_event.get("campaign_id", ""),
                "revenue": revenue_event.get("net_amount", 0),
                "model": "FIRST_TOUCH",
                "path": attribution_path,
            }

        return {"deal_id": deal_id, "attributed": False, "reason": "no_attribution_path"}

    # ─── CONTENT PERFORMANCE ──────────────────────────────────────

    def compute_content_performance(self) -> List[Dict[str, Any]]:
        """
        Rank content assets by attributed revenue, lead volume, and conversion.
        All metrics are event-derived.
        """
        deals = self.repo.list_deal_submissions()
        revenue_events = self.repo.get_revenue_events()

        # Build content → deals mapping
        content_deals: Dict[str, List[Dict]] = defaultdict(list)
        for deal in deals:
            content_id = deal.get("content_id", "")
            if content_id:
                content_deals[content_id].append(deal)

        # Build content → revenue mapping
        content_revenue: Dict[str, float] = defaultdict(float)
        for event in revenue_events:
            content_id = event.get("content_id", "")
            if content_id:
                content_revenue[content_id] += event.get("net_amount", 0)

        performance = []
        for content_id, cdeals in content_deals.items():
            total = len(cdeals)
            closed = sum(1 for d in cdeals if d.get("status") == "CLOSED")
            conversion_rate = (closed / total * 100) if total > 0 else 0

            performance.append({
                "content_id": content_id,
                "total_leads": total,
                "closed_deals": closed,
                "conversion_rate": round(conversion_rate, 1),
                "attributed_revenue": round(content_revenue.get(content_id, 0), 2),
            })

        performance.sort(key=lambda x: x["attributed_revenue"], reverse=True)
        return performance

    # ─── CAMPAIGN PERFORMANCE ─────────────────────────────────────

    def compute_campaign_performance(self) -> List[Dict[str, Any]]:
        """Aggregate content performance by campaign."""
        content_perf = self.compute_content_performance()
        deals = self.repo.list_deal_submissions()

        campaign_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_leads": 0, "closed_deals": 0, "attributed_revenue": 0
        })

        for deal in deals:
            campaign_id = deal.get("campaign_id", "")
            if campaign_id:
                campaign_stats[campaign_id]["total_leads"] += 1
                if deal.get("status") == "CLOSED":
                    campaign_stats[campaign_id]["closed_deals"] += 1

        revenue_events = self.repo.get_revenue_events()
        for event in revenue_events:
            campaign_id = event.get("campaign_id", "")
            if campaign_id:
                campaign_stats[campaign_id]["attributed_revenue"] += event.get("net_amount", 0)

        results = []
        for campaign_id, stats in campaign_stats.items():
            total = stats["total_leads"]
            closed = stats["closed_deals"]
            results.append({
                "campaign_id": campaign_id,
                "total_leads": total,
                "closed_deals": closed,
                "conversion_rate": round((closed / total * 100) if total > 0 else 0, 1),
                "attributed_revenue": round(stats["attributed_revenue"], 2),
            })

        results.sort(key=lambda x: x["attributed_revenue"], reverse=True)
        return results


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for content attribution."""
    import sys
    import json

    engine = ContentAttributionEngine()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ad_content_attribution.py [--content-performance|--campaign-performance]"}))
        return

    cmd = sys.argv[1]
    if cmd == "--content-performance":
        print(json.dumps(engine.compute_content_performance(), default=str))
    elif cmd == "--campaign-performance":
        print(json.dumps(engine.compute_campaign_performance(), default=str))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
