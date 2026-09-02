import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mbm_social.models.campaign import normalize_provider_campaign, CampaignType
from mbm_social.models.snapshot import CampaignSnapshot, detect_changes
from mbm_social.economics import EconomicAssumptions
from mbm_social.campaign_ranking import rank_campaign

def main():
    # 1. Mocked provider data
    raw_provider_campaign = {
        "brand": "Example Brand",
        "topic": "education",
        "title": "Example Campaign",
        "type": "CPM",
        "status": "ACTIVE",
        "budget_total": 15000.0,
        "budget_remaining": 12400.0,
        "payout_rate": 2.00,
        "min_duration_s": 20,
        "max_duration_s": 60,
    }

    print("--- 1. Provider Campaign ---")
    print(raw_provider_campaign)
    
    # 2. Normalize & Validate
    camp = normalize_provider_campaign("whop", "camp_demo", raw_provider_campaign)
    print("\n--- 2. Normalize & Validate ---")
    print(f"ID: {camp.id}, Type: {camp.campaign_type.value}, Status: {camp.status.value}")
    
    # 3. Snapshot
    snap_old = CampaignSnapshot.from_campaign(camp, "snap_1")
    
    # 4. Detect Changes (Simulate a budget change)
    camp.budget_remaining -= 1000.0
    snap_new = CampaignSnapshot.from_campaign(camp, "snap_2")
    
    changes = detect_changes(snap_old, snap_new)
    print("\n--- 3. Snapshot & Detect Changes ---")
    for change in changes:
        print(f"Detected {change.change_type.value}: {change.message}")
        
    # 5 & 6 & 7 & 8. Economics, Risk, Rank, Explainable Recommendation
    # We pass assumptions based on the example in the user's prompt (150,000 estimated views)
    assumptions = EconomicAssumptions(
        estimated_views_base=150000.0, 
        production_time_hours_base=2.0,
        human_hourly_rate_usd=25.0,
        ai_generation_cost_usd=5.0,
        approval_probability_base=0.9
    )
    
    res = rank_campaign(camp, assumptions)
    
    print("\n--- 4. Final Recommendation (Acceptance Output) ---")
    print("NEXT BEST CAMPAIGN\n")
    print(f"Campaign: {res.campaign_title}")
    print(f"Type: {res.campaign_type}\n")
    print(f"Remaining Budget: ${res.remaining_budget:,.2f}")
    print(f"CPM: ${res.cpm_or_rate:.2f}")
    print(f"Estimated Views: {res.estimated_views:,.0f}")
    print(f"Expected Gross: ${res.gross_expected:,.2f}")
    print(f"Estimated Fees: ${res.estimated_fees:,.2f}")
    print(f"Estimated Production Cost: ${res.production_cost:,.2f}\n")
    
    print(f"Expected Net Profit: ${res.expected_profit:,.2f}")
    print(f"Expected Profit/Hour: ${res.expected_profit_per_hour:,.2f}\n")
    
    print(f"Priority: {res.priority_score}/100")
    print(f"Risk: {res.risk_level.value}\n")
    
    print("Recommendation:")
    print(res.recommendation.value)
    
    print("\nReasons:")
    for i, reason in enumerate(res.reasons, 1):
        print(f"{i}. {reason}")
        
    print("\nWarnings:")
    if not res.warnings:
        print("None")
    for i, warning in enumerate(res.warnings, 1):
        print(f"{i}. {warning}")

if __name__ == "__main__":
    main()
