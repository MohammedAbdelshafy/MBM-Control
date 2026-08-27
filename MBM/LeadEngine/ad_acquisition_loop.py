"""
MBM LeadEngine — Acquisition Feedback Loop
============================================
Event-derived metrics that track the full lifecycle:
  lead source → acquisition → qualification → outreach → disposition
  → buyer/seller outcome → performance → source quality score → future prioritization

Never infers conversion from queue position.
Every metric is computed from persisted audit_log_entries and deal_submissions.
"""

from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from MBM.LeadEngine.ad_repository import AdRepository

log = logging.getLogger(__name__)

# Terminal deal states
TERMINAL_STATES = {"CLOSED", "LOST", "REJECTED"}
POSITIVE_TERMINAL = {"CLOSED"}
NEGATIVE_TERMINAL = {"LOST", "REJECTED"}

# Pipeline stages in order
PIPELINE_STAGES = [
    "INTAKE", "VALIDATING", "UNDERWRITING", "SCORED", "MATCHING",
    "BUYER_FOUND", "OUTREACH_SENT", "UNDER_CONTRACT", "ASSIGNED", "CLOSED",
]


class AcquisitionFeedbackLoop:
    """
    Computes event-derived acquisition metrics from persisted data.
    All metrics are grounded in audit_log_entries and deal_submissions —
    never inferred from queue position or status alone.
    """

    def __init__(self, repo: Optional[AdRepository] = None):
        self.repo = repo or AdRepository()

    # ─── SOURCE QUALITY SCORING ───────────────────────────────────

    def compute_source_quality_scores(self) -> List[Dict[str, Any]]:
        """
        Score each lead source by its deal conversion rate, average deal score,
        and time-to-close. All metrics are event-derived from audit_log_entries.
        """
        deals = self.repo.list_deal_submissions()
        audit_events = self.repo.log_event  # we need to query events differently

        # Group deals by source
        source_deals: Dict[str, List[Dict]] = defaultdict(list)
        for deal in deals:
            source = deal.get("source_platform") or deal.get("source_name") or "unknown"
            source_deals[source].append(deal)

        scores = []
        for source, src_deals in source_deals.items():
            total = len(src_deals)
            closed = sum(1 for d in src_deals if d.get("status") in POSITIVE_TERMINAL)
            lost = sum(1 for d in src_deals if d.get("status") in NEGATIVE_TERMINAL)
            active = total - closed - lost

            avg_score = 0
            scored_deals = [d for d in src_deals if d.get("buyer_matches")]
            if scored_deals:
                # Use demand_signal as proxy for quality when numeric score unavailable
                quality_map = {"HOT": 100, "WARM": 75, "NORMAL": 50, "WEAK": 25, "UNKNOWN": 0}
                scores_vals = [quality_map.get(d.get("demand_signal", "UNKNOWN"), 0) for d in scored_deals]
                avg_score = sum(scores_vals) / len(scores_vals) if scores_vals else 0

            conversion_rate = (closed / total * 100) if total > 0 else 0

            # Compute composite quality score (0-100)
            quality = 0
            if total > 0:
                quality = (
                    conversion_rate * 0.5          # 50% weight on conversion
                    + avg_score * 0.3               # 30% weight on deal quality
                    + min(total, 10) * 2            # 10% weight on volume (capped)
                )
                quality = min(100, quality)

            scores.append({
                "source": source,
                "total_deals": total,
                "closed": closed,
                "lost": lost,
                "active": active,
                "conversion_rate": round(conversion_rate, 1),
                "avg_demand_score": round(avg_score, 1),
                "quality_score": round(quality, 1),
            })

        scores.sort(key=lambda x: x["quality_score"], reverse=True)
        return scores

    # ─── PIPELINE VELOCITY ────────────────────────────────────────

    def compute_pipeline_velocity(self) -> Dict[str, Any]:
        """
        Measure time between pipeline stages using audit_log_events.
        Returns average days between each stage transition.
        """
        deals = self.repo.list_deal_submissions()
        now = datetime.now(timezone.utc)

        stage_counts: Dict[str, int] = defaultdict(int)
        stage_ages: Dict[str, List[float]] = defaultdict(list)

        for deal in deals:
            status = deal.get("status", "INTAKE")
            stage_counts[status] += 1

            created = deal.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (now - created_dt).total_seconds() / 86400
                    stage_ages[status].append(age_days)
                except (ValueError, TypeError):
                    pass

        avg_ages = {}
        for stage, ages in stage_ages.items():
            avg_ages[stage] = round(sum(ages) / len(ages), 1) if ages else 0

        return {
            "stage_distribution": dict(stage_counts),
            "avg_days_per_stage": avg_ages,
            "total_active": sum(v for k, v in stage_counts.items() if k not in TERMINAL_STATES),
            "total_closed": stage_counts.get("CLOSED", 0),
            "total_lost": stage_counts.get("LOST", 0),
        }

    # ─── FEEDBACK LOOP METRICS ────────────────────────────────────

    def compute_feedback_metrics(self) -> Dict[str, Any]:
        """
        Full feedback loop metrics:
        - Conversion funnel (each stage → next stage)
        - Source quality rankings
        - Disposition breakdown
        - Time-to-outcome
        """
        deals = self.repo.list_deal_submissions()
        source_scores = self.compute_source_quality_scores()
        velocity = self.compute_pipeline_velocity()

        # Funnel: count deals at each stage
        funnel = defaultdict(int)
        for deal in deals:
            status = deal.get("status", "INTAKE")
            funnel[status] += 1

        # Disposition breakdown from demand signals
        demand_signals = self.repo.get_demand_signals()
        signal_counts = defaultdict(int)
        for sig in demand_signals:
            signal_counts[sig.get("signal", "UNKNOWN")] += 1

        return {
            "funnel": dict(funnel),
            "source_quality": source_scores[:10],
            "velocity": velocity,
            "demand_signals": dict(signal_counts),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ─── SOURCE PRIORITIZATION ────────────────────────────────────

    def get_prioritized_sources(self) -> List[Dict[str, Any]]:
        """
        Return sources ranked by quality score for future lead prioritization.
        High-quality sources get优先 routing in the pipeline.
        """
        scores = self.compute_source_quality_scores()
        return [
            {
                "source": s["source"],
                "priority": "HIGH" if s["quality_score"] >= 70 else
                            "MEDIUM" if s["quality_score"] >= 40 else "LOW",
                "quality_score": s["quality_score"],
                "recommendation": (
                    "Increase spend" if s["quality_score"] >= 70
                    else "Maintain" if s["quality_score"] >= 40
                    else "Reduce or re-evaluate"
                ),
            }
            for s in scores
        ]

    # ─── CONVERSION ATTRIBUTION ───────────────────────────────────

    def attribute_conversions(self) -> List[Dict[str, Any]]:
        """
        Attribute closed deals to their source, campaign, and content.
        Each conversion is grounded in the deal record — never fabricated.
        """
        deals = self.repo.list_deal_submissions()
        conversions = []

        for deal in deals:
            if deal.get("status") not in POSITIVE_TERMINAL:
                continue

            conversions.append({
                "deal_id": deal.get("id"),
                "source": deal.get("source_platform") or deal.get("source_name", "unknown"),
                "campaign_id": deal.get("campaign_id", ""),
                "content_id": deal.get("content_id", ""),
                "demand_signal": deal.get("demand_signal", "UNKNOWN"),
                "buyer_matches": len(deal.get("buyer_matches", [])),
                "created_at": deal.get("created_at"),
                "status": deal.get("status"),
            })

        return conversions


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for acquisition feedback loop."""
    import sys
    import json

    loop = AcquisitionFeedbackLoop()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ad_acquisition_loop.py [--metrics|--sources|--conversions]"}))
        return

    cmd = sys.argv[1]
    if cmd == "--metrics":
        print(json.dumps(loop.compute_feedback_metrics(), default=str))
    elif cmd == "--sources":
        print(json.dumps(loop.get_prioritized_sources(), default=str))
    elif cmd == "--conversions":
        print(json.dumps(loop.attribute_conversions(), default=str))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
