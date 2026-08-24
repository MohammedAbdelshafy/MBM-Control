import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root_dir))

from MBM.LeadEngine.buyer_discovery_engine import BuyerDiscoveryEngine
from MBM.LeadEngine.buyer_matching_engine import BuyerMatchingEngine
from MBM.LeadEngine.daily_lead_factory import DailyLeadFactory

def main():
    print("--- BUYER DISCOVERY ---")
    buyer_engine = BuyerDiscoveryEngine()
    active_buyers = buyer_engine.discover_active_buyers()
    print(f"Found {len(active_buyers)} active buyers.")
    for b in active_buyers:
        print(f"  - {b.company} ({b.buyer_id}) | {b.market} | Min Acres: {b.min_acres} | Zoning: {b.zoning}")

    print("\n--- FACTORY DRY-RUN ---")
    # Instead of running the full pipeline, we'll just run _load_real_candidate_pool 
    # to see what matched from the real property artifacts.
    factory = DailyLeadFactory()
    pool = factory._load_real_candidate_pool()
    
    # Check how many properties got a buyer match
    matched = [c for c in pool if c.get("buyer_match_score")]
    print(f"\nFound {len(matched)} properties matched to buyers out of {len(pool)} total real pool candidates.")
    for c in matched[:5]:
        print(f"  - Property {c.get('parcel_id', c.get('id'))} matched {c.get('buyer_id')} (Score: {c.get('buyer_match_score')}) | Demand: {c.get('buyer_demand')}")

if __name__ == "__main__":
    main()
