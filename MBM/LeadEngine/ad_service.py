"""
MBM LeadEngine — Acquisition-Disposition Service
==================================================
Application service layer that wires domain engines to the repository.
Engines remain pure/persistent-agnostic. This layer handles persistence.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from MBM.LeadEngine.ad_repository import AdRepository

log = logging.getLogger(__name__)
from MBM.LeadEngine.buyer_buy_box_engine import BuyerBuyBoxEngine, BuyerBuyBox
from MBM.LeadEngine.deal_scoring_engine import DealScoringEngine, DealScore
from MBM.LeadEngine.deal_submission_engine import DealSubmissionEngine, DealSubmission
from MBM.LeadEngine.social_cta_router import SocialCTARouter, SocialInteraction
from MBM.LeadEngine.next_best_action_engine import NextBestActionEngine, NextAction


class AdService:
    """
    Application service for the Acquisition-Disposition engine.
    Wires domain engines to persistence via AdRepository.
    """

    def __init__(self, repo: Optional[AdRepository] = None):
        self.repo = repo or AdRepository()
        self.buy_box_engine = BuyerBuyBoxEngine()
        self.deal_scoring = DealScoringEngine()
        self.deal_submission = DealSubmissionEngine()
        self.social_router = SocialCTARouter()
        self.next_action_engine = NextBestActionEngine()
        self._sync_buyers_to_engine()

    def _sync_buyers_to_engine(self):
        """Load persisted buyers into the in-memory engine for matching."""
        buyers = self.repo.list_buyer_buy_boxes()
        loaded = 0
        for b in buyers:
            try:
                bb = BuyerBuyBox(**{k: v for k, v in b.items() if k in BuyerBuyBox.__dataclass_fields__})
                self.buy_box_engine.buyers[bb.buyer_id] = bb
                loaded += 1
            except Exception as e:
                log.warning("Failed to load buyer %s: %s", b.get("buyer_id", "?"), e)
        log.info("Synced %d/%d buyers to engine", loaded, len(buyers))

    # ─── DEMAND SIGNAL HELPERS ─────────────────────────────────────

    @staticmethod
    def _classify_demand(active_count: int, verified_count: int) -> str:
        """Classify demand signal from buyer counts. Single source of truth."""
        if active_count >= 5:
            return "HOT"
        elif active_count >= 3:
            return "WARM"
        elif active_count >= 1:
            return "NORMAL"
        elif verified_count >= 1:
            return "WEAK"
        return "UNKNOWN"

    def _compute_segment_demand(self, market: str, property_type: str,
                                price_min: float, price_max: float) -> Dict[str, Any]:
        """Compute demand signal for a market/property/price segment from repo."""
        buyers_in_segment = self.repo.get_buyers_for_segment(market, property_type, price_min, price_max)
        active = [b for b in buyers_in_segment if b.get("activity_score", 0) >= 50]
        verified = [b for b in buyers_in_segment if b.get("verification_status") == "VERIFIED"]
        signal = self._classify_demand(len(active), len(verified))
        return {
            "signal": signal,
            "active_buyers": len(active),
            "verified_buyers": len(verified),
            "total_buyers": len(buyers_in_segment),
        }

    # ─── DEAL SUBMISSION + SCORING + MATCHING ──────────────────────

    def submit_and_score_deal(self, deal: DealSubmission) -> Dict[str, Any]:
        """
        Full deal submission flow:
        1. Persist → 2. Validate → 3. Score → 4. Match → 5. NBA → 6. Persist results
        """
        # 1. Persist deal
        deal_data = deal.to_dict()
        deal_data["status"] = "INTAKE"
        self.repo.insert_deal_submission(deal_data)

        # 2. Validate
        validation = self.deal_submission.validate_deal(deal)

        if not validation.is_valid:
            self.repo.update_deal_submission(deal.id, {
                "status": "VALIDATING",
                "validation_errors": validation.missing_critical,
                "validation_warnings": validation.warnings,
            })
            self.repo.log_event("deal_validation_failed", deal.id, "deal",
                               payload={"errors": validation.missing_critical})
            return {
                "deal_id": deal.id,
                "status": "VALIDATION_FAILED",
                "validation": validation.to_dict(),
                "next_action": "COLLECT_MISSING_DATA",
            }

        # 3. Score
        deal_dict = self.deal_submission.to_deal_dict(deal)

        # Get demand from repo (persistent, not in-memory)
        price_min = deal.asking_price * 0.7 if deal.asking_price else 0
        price_max = deal.asking_price * 1.3 if deal.asking_price else 0
        seg = self._compute_segment_demand(deal.city, deal.property_type, price_min, price_max)
        demand_signal = seg["signal"]

        score = self.deal_scoring.score_deal(
            deal_dict,
            demand_signal=demand_signal,
            active_buyers=seg["total_buyers"],
        )

        # 4. Match buyers — reload ALL buyers from repo (don't wipe engine)
        self._sync_buyers_to_engine()
        matches = self.buy_box_engine.match_deal_to_buyers(deal_dict, top_n=10)
        match_dicts = [m.to_dict() for m in matches]

        # 5. Transition status
        if score.quality_grade in ("INCOMPLETE", "D"):
            new_status = "REJECTED"
        else:
            new_status = "SCORED"

        self.repo.update_deal_submission(deal.id, {
            "status": new_status,
            "demand_signal": demand_signal,
            "buyer_matches": match_dicts,
            "validation_errors": [],
            "validation_warnings": validation.warnings,
        })

        # 6. Persist demand signal
        self.repo.upsert_demand_signal({
            "market": deal.city,
            "property_type": deal.property_type,
            "price_band": f"${(deal.asking_price*0.7/1000):.0f}K-${(deal.asking_price*1.3/1000):.0f}K",
            "signal": demand_signal,
            "active_buyers": seg["active_buyers"],
            "verified_buyers": seg["verified_buyers"],
        })

        # 7. Generate next-best-action
        nba_data = {
            "id": deal.id,
            "status": new_status,
            "deal_score": score.overall_score,
            "buyer_matches_count": len(matches),
        }
        action = self.next_action_engine.compute_deal_action(nba_data)

        nba_record = {
            "entity_id": deal.id,
            "entity_type": "deal",
            "action": action.action,
            "priority": action.priority,
            "reason": action.reason,
            "deadline": action.deadline,
            "status": "PENDING",
        }
        self.repo.upsert_next_best_action(nba_record)

        # 8. Audit log
        self.repo.log_event("deal_scored", deal.id, "deal",
                           payload={
                               "score": score.overall_score,
                               "grade": score.quality_grade,
                               "demand": demand_signal,
                               "matches": len(matches),
                           })

        return {
            "deal_id": deal.id,
            "status": new_status,
            "validation": validation.to_dict(),
            "score": score.to_dict(),
            "buyer_matches": match_dicts,
            "demand_signal": demand_signal,
            "next_action": action.to_dict(),
        }

    # ─── BUYER REGISTRATION ────────────────────────────────────────

    def register_buyer(self, buyer: BuyerBuyBox) -> Dict[str, Any]:
        """Register a buyer and persist to database."""
        # Persist buy box
        self.repo.upsert_buyer_buy_box(buyer.to_dict())

        # Sync to in-memory engine for matching
        self.buy_box_engine.buyers[buyer.buyer_id] = buyer

        # Calculate demand for buyer's segments from repo
        demand_signals = []
        for market in buyer.markets:
            for ptype in buyer.property_types:
                seg = self._compute_segment_demand(market, ptype, buyer.price_min, buyer.price_max)
                self.repo.upsert_demand_signal({
                    "market": market,
                    "property_type": ptype,
                    "price_band": f"${buyer.price_min/1000:.0f}K-${buyer.price_max/1000:.0f}K",
                    "signal": seg["signal"],
                    "active_buyers": seg["active_buyers"],
                    "verified_buyers": seg["verified_buyers"],
                })
                demand_signals.append({"market": market, "property_type": ptype, "signal": seg["signal"]})

        # Generate NBA
        action = self.next_action_engine.compute_buyer_action({
            "id": buyer.buyer_id,
            "has_buy_box": buyer.completeness_score() > 50,
            "buy_box_completeness": buyer.completeness_score(),
            "activity_score": buyer.activity_score,
            "verification_status": buyer.verification_status,
            "matched_deals_count": 0,
        })

        self.repo.upsert_next_best_action({
            "entity_id": buyer.buyer_id,
            "entity_type": "buyer",
            "action": action.action,
            "priority": action.priority,
            "reason": action.reason,
            "deadline": action.deadline,
            "status": "PENDING",
        })

        self.repo.log_event("buyer_registered", buyer.buyer_id, "buyer",
                           payload={"completeness": buyer.completeness_score()})

        return {
            "buyer_id": buyer.buyer_id,
            "completeness": buyer.completeness_score(),
            "demand_signals": demand_signals,
            "action": action.to_dict(),
        }

    # ─── SOCIAL ROUTING ────────────────────────────────────────────

    def route_social_interaction(self, interaction: SocialInteraction) -> Dict[str, Any]:
        """Route social interaction and persist."""
        # Route
        routing = self.social_router.route_interaction(interaction)

        # Persist
        self.repo.insert_social_interaction(interaction.to_dict())

        # Compute NBA
        entity = {
            "id": interaction.id,
            "status": "NEW",
            "motivation_score": 50 if routing.priority == "HOT" else 30,
            "has_buy_box": False,
            "buy_box_completeness": 0,
            "activity_score": 50 if routing.priority == "HOT" else 30,
            "verification_status": "UNVERIFIED",
            "has_submitted_deal": False,
            "last_contact_at": interaction.created_at,
        }
        action = self.next_action_engine.compute_action(routing.lead_type, entity)

        self.repo.upsert_next_best_action({
            "entity_id": interaction.id,
            "entity_type": routing.lead_type,
            "action": action.action,
            "priority": action.priority,
            "reason": action.reason,
            "deadline": action.deadline,
            "status": "PENDING",
        })

        self.repo.log_event("social_routed", interaction.id, routing.lead_type,
                           payload={"platform": interaction.platform, "intent": routing.intent})

        return {
            "interaction_id": interaction.id,
            "routing": routing.to_dict(),
            "action": action.to_dict(),
        }

    # ─── FOLLOW-UP MANAGEMENT ──────────────────────────────────────

    def create_follow_up(self, entity_id: str, entity_type: str, reason: str,
                         priority: int = 3, channel: str = "MANUAL",
                         scheduled_at: Optional[str] = None, owner: str = "system") -> Dict[str, Any]:
        """Create a follow-up task."""
        data = {
            "id": str(uuid.uuid4()),
            "entity_id": entity_id,
            "entity_type": entity_type,
            "reason": reason,
            "priority": priority,
            "channel": channel,
            "status": "PENDING",
            "scheduled_at": scheduled_at or (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "next_attempt": scheduled_at or (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "owner": owner,
        }
        persisted = self.repo.insert_follow_up(data)
        self.repo.log_event("followup_created", entity_id, entity_type,
                           payload={"channel": channel, "reason": reason})
        return persisted

    def get_pending_follow_ups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get pending follow-ups."""
        return self.repo.get_pending_follow_ups(limit)

    # ─── PIPELINE SNAPSHOT ─────────────────────────────────────────

    def get_pipeline_snapshot(self) -> Dict[str, Any]:
        """Get full pipeline state from persistence."""
        # Buyers
        buyers = self.repo.list_buyer_buy_boxes()
        active_buyers = [b for b in buyers if b.get("verification_status") in ("VERIFIED", "PROBABLE")]

        # Deals
        deals = self.repo.list_deal_submissions()
        active_deals = [d for d in deals if d.get("status") not in ("CLOSED", "LOST", "REJECTED")]

        # Demand
        demand = self.repo.get_demand_signals()

        # NBA
        pending_actions = self.repo.get_next_best_actions("PENDING", 20)
        critical = [a for a in pending_actions if a.get("priority", 5) <= 2]

        # Follow-ups
        follow_ups = self.repo.get_pending_follow_ups(10)

        # Deals by status
        status_counts: Dict[str, int] = {}
        for d in deals:
            s = d.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total_buyers": len(buyers),
            "active_buyers": len(active_buyers),
            "verified_buyers": len([b for b in buyers if b.get("verification_status") == "VERIFIED"]),
            "total_deals": len(deals),
            "active_deals": len(active_deals),
            "deals_by_status": status_counts,
            "demand_signals": demand,
            "hot_segments": len([d for d in demand if d.get("signal") == "HOT"]),
            "pending_actions": pending_actions,
            "critical_actions": len(critical),
            "pending_follow_ups": len(follow_ups),
            "follow_ups": follow_ups,
        }

    # ─── DISPOSITION VIEW ──────────────────────────────────────────

    def get_disposition_view(self) -> Dict[str, Any]:
        """Get disposition command center data."""
        deals = self.repo.get_active_deals()

        deals_with_actions = []
        for deal in deals:
            action = self.next_action_engine.compute_deal_action({
                "id": deal.get("id"),
                "status": deal.get("status", "INTAKE"),
                "deal_score": 0,
                "buyer_matches_count": len(deal.get("buyer_matches", [])),
                "outreach_sent_count": 0,
                "response_count": 0,
                "days_active": 0,
            })
            deals_with_actions.append({
                "deal": deal,
                "action": action.to_dict(),
            })

        deals_with_actions.sort(key=lambda x: x["action"]["priority"])

        return {
            "total_active": len(deals),
            "deals": deals_with_actions,
        }

    # ─── DEMAND DASHBOARD ──────────────────────────────────────────

    def get_demand_dashboard(self) -> Dict[str, Any]:
        """Get full demand dashboard."""
        signals = self.repo.get_demand_signals()

        market_demand: Dict[str, List[Dict]] = {}
        for signal in signals:
            market = signal.get("market", "Unknown")
            if market not in market_demand:
                market_demand[market] = []
            market_demand[market].append(signal)

        return {
            "total_segments": len(signals),
            "hot_segments": len([s for s in signals if s.get("signal") == "HOT"]),
            "warm_segments": len([s for s in signals if s.get("signal") == "WARM"]),
            "market_demand": market_demand,
            "signals": signals,
        }

    # ─── REVENUE ATTRIBUTION ───────────────────────────────────────

    def record_revenue(self, deal_id: str, revenue_type: str, gross_amount: float,
                       fees: float = 0, source_id: str = "", campaign_id: str = "",
                       content_id: str = "", buyer_id: str = "",
                       attribution_path: Optional[List[str]] = None) -> Dict[str, Any]:
        """Record a revenue event with attribution."""
        data = {
            "deal_id": deal_id,
            "revenue_type": revenue_type,
            "gross_amount": gross_amount,
            "fees": fees,
            "net_amount": gross_amount - fees,
            "currency": "USD",
            "status": "PENDING",
            "source_id": source_id,
            "campaign_id": campaign_id,
            "content_id": content_id,
            "buyer_id": buyer_id,
            "attribution_path": attribution_path or [],
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted = self.repo.insert_revenue_event(data)
        self.repo.log_event("revenue_recorded", deal_id, "deal",
                           payload={"type": revenue_type, "amount": gross_amount})
        return persisted
