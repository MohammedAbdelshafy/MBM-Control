"""
MBM LeadEngine — Acquisition-Disposition Orchestrator v2
=========================================================
Ties together all engines via the service layer.
This is the single entry point for the revenue-oriented AD operating system.
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from MBM.LeadEngine.ad_service import AdService
from MBM.LeadEngine.ad_repository import AdRepository
from MBM.LeadEngine.buyer_buy_box_engine import BuyerBuyBox
from MBM.LeadEngine.deal_submission_engine import DealSubmission
from MBM.LeadEngine.social_cta_router import SocialInteraction


class AcquisitionDispositionOrchestrator:
    """
    Main orchestrator for the acquisition-disposition engine.
    Uses AdService for persistence. Engines remain pure.
    """

    def __init__(self, repo: Optional[AdRepository] = None):
        self.repo = repo or AdRepository()
        self.service = AdService(self.repo)

    # ─── DEAL FLOW ─────────────────────────────────────────────────

    def submit_deal(self, deal: DealSubmission) -> Dict[str, Any]:
        """End-to-end deal submission: validate → score → match → persist."""
        return self.service.submit_and_score_deal(deal)

    # ─── BUYER FLOW ────────────────────────────────────────────────

    def register_buyer(self, buyer: BuyerBuyBox) -> Dict[str, Any]:
        """Register buyer and update demand signals."""
        return self.service.register_buyer(buyer)

    # ─── SOCIAL FLOW ───────────────────────────────────────────────

    def route_social(self, interaction: SocialInteraction) -> Dict[str, Any]:
        """Route social interaction to correct pipeline."""
        return self.service.route_social_interaction(interaction)

    # ─── DASHBOARDS ────────────────────────────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        """Full pipeline snapshot."""
        return self.service.get_pipeline_snapshot()

    def demand_dashboard(self) -> Dict[str, Any]:
        """Demand command center."""
        return self.service.get_demand_dashboard()

    def disposition_view(self) -> Dict[str, Any]:
        """Disposition command center."""
        return self.service.get_disposition_view()

    def today_actions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Today's highest-value actions."""
        return self.repo.get_next_best_actions("PENDING", limit)

    def pending_follow_ups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Pending follow-up tasks."""
        return self.service.get_pending_follow_ups(limit)

    # ─── REVENUE ───────────────────────────────────────────────────

    def record_revenue(self, deal_id: str, revenue_type: str, gross_amount: float,
                       **kwargs) -> Dict[str, Any]:
        """Record revenue with attribution."""
        return self.service.record_revenue(deal_id, revenue_type, gross_amount, **kwargs)

    def revenue_report(self) -> Dict[str, Any]:
        """Revenue summary."""
        events = self.repo.get_revenue_events()
        total_gross = sum(e.get("gross_amount", 0) for e in events)
        total_fees = sum(e.get("fees", 0) for e in events)
        total_net = sum(e.get("net_amount", 0) for e in events)
        return {
            "total_events": len(events),
            "total_gross": total_gross,
            "total_fees": total_fees,
            "total_net": total_net,
            "by_type": {},
        }


def main():
    """CLI entry point."""
    orch = AcquisitionDispositionOrchestrator()

    if len(sys.argv) < 2:
        print("Usage: python ad_orchestrator.py [snapshot|demand|disposition|today|revenue|submit-deal|route-social]")
        return

    cmd = sys.argv[1]

    if cmd == "snapshot":
        print(json.dumps(orch.snapshot(), indent=2, default=str))
    elif cmd == "demand":
        print(json.dumps(orch.demand_dashboard(), indent=2, default=str))
    elif cmd == "disposition":
        print(json.dumps(orch.disposition_view(), indent=2, default=str))
    elif cmd == "today":
        print(json.dumps(orch.today_actions(), indent=2, default=str))
    elif cmd == "revenue":
        print(json.dumps(orch.revenue_report(), indent=2, default=str))
    elif cmd == "submit-deal":
        deal = DealSubmission(
            address="123 Main St", city="Houston", state="TX",
            zip_code="77001", property_type="SFR",
            asking_price=150000, arv=250000, estimated_repairs=30000,
            source_platform="instagram", source_name="demo_wholesaler",
        )
        print(json.dumps(orch.submit_deal(deal), indent=2, default=str))
    elif cmd == "route-social":
        interaction = SocialInteraction(
            platform="instagram", username="test_user",
            message="I have a DEAL in Houston, SFR, asking $150K",
        )
        print(json.dumps(orch.route_social(interaction), indent=2, default=str))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
