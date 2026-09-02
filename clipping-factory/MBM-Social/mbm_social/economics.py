from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional

from .models.campaign import NormalizedCampaign, CampaignType

class Scenario(Enum):
    PESSIMISTIC = "PESSIMISTIC"
    BASE = "BASE"
    OPTIMISTIC = "OPTIMISTIC"

@dataclass
class EconomicAssumptions:
    # Explicit, configurable assumptions.
    # No arbitrary internet claims allowed.
    estimated_views_pessimistic: float = 500.0
    estimated_views_base: float = 5000.0
    estimated_views_optimistic: float = 50000.0
    
    # Production time
    production_time_hours_pessimistic: float = 2.0
    production_time_hours_base: float = 1.0
    production_time_hours_optimistic: float = 0.5
    
    # Costs
    human_hourly_rate_usd: float = 25.0
    ai_generation_cost_usd: float = 0.50
    platform_fixed_cost_usd: float = 0.0 # E.g., amortized SaaS cost per clip
    
    # Risk
    # Probability that the provider approves the clip and pays out
    approval_probability_pessimistic: float = 0.50
    approval_probability_base: float = 0.85
    approval_probability_optimistic: float = 0.95
    
    provider_fee_rate: float = 0.0 # E.g., Whop might take 0% of campaigns, or 20%
    
@dataclass
class EconomicProjection:
    scenario: Scenario
    
    gross_expected_revenue: float
    provider_fees: float
    net_revenue: float
    
    production_cost: float
    ai_cost: float
    platform_cost: float
    total_cost: float
    
    risk_adjustment: float # Multiplier based on approval probability
    expected_profit: float # Risk-adjusted profit
    
    profit_per_clip: float
    profit_per_hour: float

import math

def _validate_float(val: float, name: str, min_val: float = 0.0, max_val: float = float('inf')) -> float:
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"Invalid economics: {name} is NaN or infinity")
    if val < min_val:
        raise ValueError(f"Invalid economics: {name} cannot be less than {min_val}")
    if val > max_val:
        raise ValueError(f"Invalid economics: {name} cannot exceed {max_val}")
    return val

def calculate_scenario_economics(
    campaign: NormalizedCampaign, 
    assumptions: EconomicAssumptions, 
    scenario: Scenario
) -> EconomicProjection:
    """
    Calculates the economics for a specific scenario.
    """
    if scenario == Scenario.PESSIMISTIC:
        views = assumptions.estimated_views_pessimistic
        time_hours = assumptions.production_time_hours_pessimistic
        prob = assumptions.approval_probability_pessimistic
    elif scenario == Scenario.BASE:
        views = assumptions.estimated_views_base
        time_hours = assumptions.production_time_hours_base
        prob = assumptions.approval_probability_base
    else:
        views = assumptions.estimated_views_optimistic
        time_hours = assumptions.production_time_hours_optimistic
        prob = assumptions.approval_probability_optimistic
        
    views = _validate_float(views, "estimated_views")
    time_hours = _validate_float(time_hours, "production_time_hours")
    prob = _validate_float(prob, "approval_probability", max_val=1.0)
    fee_rate = _validate_float(assumptions.provider_fee_rate, "provider_fee_rate", max_val=1.0)
        
    # Cap revenue if budget remaining is less than expected
    payout = _validate_float(campaign.payout_rate, "payout_rate")
    if campaign.campaign_type == CampaignType.CPM:
        gross_rev = (views / 1000.0) * payout
    elif campaign.campaign_type == CampaignType.PER_POST:
        gross_rev = payout
    elif campaign.campaign_type == CampaignType.RETAINER:
        # Retainer implies a flat monthly/weekly rate. We might divide by expected clips.
        # For simplicity, treat payout_rate as the full retainer value per period.
        gross_rev = payout
    else:
        gross_rev = 0.0
        
    budget_remaining = _validate_float(campaign.budget_remaining, "budget_remaining")
    if campaign.budget_total > 0 and gross_rev > budget_remaining:
        gross_rev = budget_remaining
        
    provider_fees = gross_rev * fee_rate
    net_rev = gross_rev - provider_fees
    
    hr_rate = _validate_float(assumptions.human_hourly_rate_usd, "human_hourly_rate_usd")
    ai_cost = _validate_float(assumptions.ai_generation_cost_usd, "ai_generation_cost_usd")
    platform_cost = _validate_float(assumptions.platform_fixed_cost_usd, "platform_fixed_cost_usd")
    
    production_cost = time_hours * hr_rate
    total_cost = production_cost + ai_cost + platform_cost
    
    # Risk adjustment: only revenue is risk-adjusted down (might not get paid). 
    # Costs are always sunk.
    risk_adjusted_revenue = net_rev * prob
    
    expected_profit = risk_adjusted_revenue - total_cost
    profit_per_clip = expected_profit
    
    if time_hours > 0:
        profit_per_hour = expected_profit / time_hours
    else:
        profit_per_hour = float('inf') if expected_profit > 0 else float('-inf') if expected_profit < 0 else 0.0
        
    return EconomicProjection(
        scenario=scenario,
        gross_expected_revenue=gross_rev,
        provider_fees=provider_fees,
        net_revenue=net_rev,
        production_cost=production_cost,
        ai_cost=ai_cost,
        platform_cost=platform_cost,
        total_cost=total_cost,
        risk_adjustment=prob,
        expected_profit=expected_profit,
        profit_per_clip=profit_per_clip,
        profit_per_hour=profit_per_hour
    )

def calculate_economics(
    campaign: NormalizedCampaign, 
    assumptions: Optional[EconomicAssumptions] = None
) -> Dict[Scenario, EconomicProjection]:
    """
    Calculates economics across all three scenarios.
    """
    assumps = assumptions or EconomicAssumptions()
    
    _validate_float(campaign.payout_rate, "campaign.payout_rate")
    _validate_float(campaign.budget_total, "campaign.budget_total")
    _validate_float(campaign.budget_remaining, "campaign.budget_remaining")
        
    return {
        Scenario.PESSIMISTIC: calculate_scenario_economics(campaign, assumps, Scenario.PESSIMISTIC),
        Scenario.BASE: calculate_scenario_economics(campaign, assumps, Scenario.BASE),
        Scenario.OPTIMISTIC: calculate_scenario_economics(campaign, assumps, Scenario.OPTIMISTIC),
    }
