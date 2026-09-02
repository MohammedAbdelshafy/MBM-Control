from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .models.campaign import NormalizedCampaign, CampaignStatus, CampaignType
from .economics import EconomicProjection, Scenario, calculate_economics, EconomicAssumptions

class Recommendation(Enum):
    PRODUCE = "PRODUCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT = "REJECT"

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

@dataclass
class RankingResult:
    campaign_id: str
    campaign_title: str
    campaign_type: str
    
    priority_score: int # 0-100
    expected_profit: float
    expected_profit_per_hour: float
    
    risk_level: RiskLevel
    recommendation: Recommendation
    
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Financial details for display
    remaining_budget: float = 0.0
    cpm_or_rate: float = 0.0
    estimated_views: float = 0.0
    gross_expected: float = 0.0
    estimated_fees: float = 0.0
    production_cost: float = 0.0

def _calculate_risk(campaign: NormalizedCampaign, economics: Dict[Scenario, EconomicProjection]) -> RiskLevel:
    base = economics[Scenario.BASE]
    
    risk_factors = 0
    # Approval probability less than 75%
    if base.risk_adjustment < 0.75:
        risk_factors += 2
        
    # Budget remaining is low
    if campaign.campaign_type == CampaignType.CPM and base.gross_expected_revenue >= campaign.budget_remaining * 0.9:
        risk_factors += 1
        
    if risk_factors >= 2:
        return RiskLevel.HIGH
    elif risk_factors == 1:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW

def _build_reasons_and_warnings(
    campaign: NormalizedCampaign, 
    economics: Dict[Scenario, EconomicProjection],
    risk: RiskLevel,
    profit_per_hour: float
) -> tuple[List[str], List[str]]:
    reasons = []
    warnings = []
    base = economics[Scenario.BASE]
    
    # Reasons
    if campaign.budget_remaining > 5000:
        reasons.append("Strong remaining budget")
    
    if profit_per_hour > 40.0:
        reasons.append("High expected profit/hour")
    elif profit_per_hour > 20.0:
        reasons.append("Good expected profit/hour")
        
    if base.risk_adjustment > 0.90:
        reasons.append("High approval probability")
        
    if campaign.expires_at_iso:
        # Check if expires soon
        try:
            exp_date = datetime.fromisoformat(campaign.expires_at_iso.replace("Z", "+00:00"))
            days_left = (exp_date - datetime.now(timezone.utc)).days
            if 0 < days_left <= 7:
                reasons.append(f"Campaign expires soon ({days_left} days left)")
        except ValueError:
            pass
            
    # Warnings
    if risk == RiskLevel.HIGH:
        warnings.append("High risk profile (low approval probability or budget constraints)")
        
    if campaign.campaign_type == CampaignType.CPM and base.risk_adjustment < 0.8:
        warnings.append("View performance is uncertain or approval risk is high")
        
    if base.expected_profit <= 0:
        warnings.append("Expected profit is zero or negative")
        
    if campaign.budget_remaining < base.gross_expected_revenue * 1.5:
        warnings.append("Campaign budget is running low and might exhaust before payout")
        
    return reasons, warnings

def rank_campaign(
    campaign: NormalizedCampaign, 
    assumptions: Optional[EconomicAssumptions] = None
) -> RankingResult:
    """
    Evaluates a campaign and produces an explainable ranking decision.
    """
    if campaign.status != CampaignStatus.ACTIVE:
        return RankingResult(
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            campaign_type=campaign.campaign_type.value,
            priority_score=0,
            expected_profit=0.0,
            expected_profit_per_hour=0.0,
            risk_level=RiskLevel.HIGH,
            recommendation=Recommendation.REJECT,
            reasons=[],
            warnings=["Campaign is not ACTIVE"],
            remaining_budget=campaign.budget_remaining,
            cpm_or_rate=campaign.payout_rate
        )
        
    assumps = assumptions or EconomicAssumptions()
    economics = calculate_economics(campaign, assumps)
    base = economics[Scenario.BASE]
    
    risk = _calculate_risk(campaign, economics)
    
    # Priority Score logic (0-100)
    score = 0
    # Profit component (max 60 pts)
    profit_score = min(60, int((base.profit_per_hour / 100.0) * 60))
    score += max(0, profit_score)
    
    # Budget component (max 20 pts)
    budget_score = min(20, int((campaign.budget_remaining / 10000.0) * 20))
    score += max(0, budget_score)
    
    # Risk adjustment component (max 20 pts)
    risk_score_component = int(base.risk_adjustment * 20)
    score += risk_score_component
    
    score = max(0, min(100, score))
    
    reasons, warnings = _build_reasons_and_warnings(campaign, economics, risk, base.profit_per_hour)
    
    if score >= 70 and risk != RiskLevel.HIGH and base.expected_profit > 0:
        rec = Recommendation.PRODUCE
    elif base.expected_profit <= 0:
        rec = Recommendation.REJECT
    else:
        rec = Recommendation.REVIEW_REQUIRED
        
    return RankingResult(
        campaign_id=campaign.id,
        campaign_title=campaign.title,
        campaign_type=campaign.campaign_type.value,
        priority_score=score,
        expected_profit=base.expected_profit,
        expected_profit_per_hour=base.profit_per_hour,
        risk_level=risk,
        recommendation=rec,
        reasons=reasons,
        warnings=warnings,
        remaining_budget=campaign.budget_remaining,
        cpm_or_rate=campaign.payout_rate,
        estimated_views=assumps.estimated_views_base,
        gross_expected=base.gross_expected_revenue,
        estimated_fees=base.provider_fees,
        production_cost=base.total_cost
    )
