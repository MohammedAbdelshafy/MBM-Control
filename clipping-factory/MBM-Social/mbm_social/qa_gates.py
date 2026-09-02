from dataclasses import dataclass
from typing import List, Optional

from .models.source import NormalizedSource, ProvenanceConfidence
from .moment_discovery import CandidateMoment, MomentConfidence
from .clip_planner import ClipPlan, Platform
from .models.campaign import NormalizedCampaign, CampaignStatus
from .economics import EconomicAssumptions, calculate_economics, Scenario
from .campaign_ranking import Recommendation

@dataclass
class QAResult:
    recommendation: Recommendation
    reasons: List[str]
    gate_failures: List[str]

def run_qa_gates(
    source: NormalizedSource,
    moment: CandidateMoment,
    plan: ClipPlan,
    campaign: Optional[NormalizedCampaign],
    assumptions: EconomicAssumptions
) -> QAResult:
    hard_failures = []
    review_reasons = []
    
    # Gate A - Source Integrity
    if not source.source_id or not source.content_hash:
        hard_failures.append("Gate A: Missing source identity or content hash")
    if source.duration_seconds and source.duration_seconds <= 0:
        hard_failures.append("Gate A: Invalid source duration")
        
    # Gate B - Moment Integrity
    if moment.end_seconds <= moment.start_seconds or moment.start_seconds < 0:
        hard_failures.append("Gate B: Invalid moment timestamps")
    if source.duration_seconds and moment.end_seconds > source.duration_seconds:
        hard_failures.append("Gate B: Moment exceeds source duration")
    if moment.confidence in (MomentConfidence.LOW, MomentConfidence.UNKNOWN):
        review_reasons.append("Gate B: Insufficient confidence")
        
    # Gate C - Clip Plan Integrity
    if Platform.UNSUPPORTED in plan.target_platforms:
        hard_failures.append("Gate C: Unsupported platform in plan")
    if not plan.provenance_chain:
        hard_failures.append("Gate C: Missing provenance chain in plan")
        
    # Gate D - Production Safety
    if plan.target_duration <= 0:
        hard_failures.append("Gate D: Invalid target duration for production")
        
    # Gate E - Economic Safety
    if not campaign:
        hard_failures.append("Gate E: Cannot evaluate economics without a campaign")
    else:
        if campaign.status in (CampaignStatus.PAUSED, CampaignStatus.CLOSED):
            hard_failures.append("Gate E: Campaign is paused or closed")
            
        projections = calculate_economics(campaign, assumptions)
        base_proj = projections[Scenario.BASE]
        
        if base_proj.expected_profit < 0:
            hard_failures.append(f"Gate E: Expected profit is negative ({base_proj.expected_profit})")
            
        if campaign.budget_remaining <= 0:
            hard_failures.append("Gate E: Campaign budget exhausted")

    # Decision Logic
    if hard_failures:
        return QAResult(
            recommendation=Recommendation.REJECT,
            reasons=hard_failures,
            gate_failures=hard_failures
        )
        
    if review_reasons:
        return QAResult(
            recommendation=Recommendation.REVIEW_REQUIRED,
            reasons=review_reasons,
            gate_failures=[]
        )
        
    # Margin check
    if campaign:
        projections = calculate_economics(campaign, assumptions)
        base_proj = projections[Scenario.BASE]
        if base_proj.profit_per_hour < 20.0:
            return QAResult(
                recommendation=Recommendation.REVIEW_REQUIRED,
                reasons=["Passes QA but profit margin is low"],
                gate_failures=[]
            )
            
    return QAResult(
        recommendation=Recommendation.PRODUCE,
        reasons=["All QA gates passed. Economics are viable."],
        gate_failures=[]
    )
