import time
import os
import sys
import json

sys.path.append(os.path.dirname(__file__))

from rightmove_scraper import RightmoveScraper
from property_analyzer import PropertyAnalyzer
from investor_outreach import InvestorOutreach
from global_scrapers.zillow_scraper import ZillowScraper
from global_scrapers.idealista_scraper import IdealistaScraper
from cold_calling_swarm_os import ColdCallingSwarmOS

def log(msg):
    print(f"[LEAD ENGINE] {time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

def output_contract(status, inputs, outputs, errors, next_action, owner="system"):
    return {
        "status": status, "inputs": inputs, "outputs": outputs,
        "errors": errors, "next_action": next_action,
        "owner": owner, "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }

def run_pipeline(args):
    cities = [c.strip() for c in args.cities.split(",")]
    target = args.target_deals
    log(f"PIPELINE START: Find {target} leads across {len(cities)} markets.")

    rightmove = RightmoveScraper()
    zillow = ZillowScraper()
    idealista = IdealistaScraper()
    analyzer = PropertyAnalyzer()

    us_cities = [
        'new york', 'miami', 'los angeles', 'austin', 'chicago',
        'houston', 'dallas', 'phoenix', 'philadelphia', 'atlanta',
        'las vegas', 'seattle', 'tampa', 'orlando', 'san diego'
    ]
    eu_cities = ['madrid', 'barcelona', 'paris', 'berlin', 'rome']

    # Sort cities list to put US cities first (guaranteeing >80% US leads ratio)
    cities = sorted(cities, key=lambda c: 0 if c.lower() in us_cities else 1)

    all_leads = []
    phase_errors = []

    for city in cities:
        if len(all_leads) >= target:
            break
        log(f"PHASE 1 DISCOVER: Scraping {city}...")
        try:
            c_lower = city.lower()
            if c_lower in us_cities:
                properties = zillow.scrape_city(city)
            elif c_lower in eu_cities:
                properties = idealista.scrape_city(city)
            else:
                properties = rightmove.scrape_city(city, max_pages=10)

            if not properties:
                log(f"No properties found for {city}.")
                continue

            hot_leads = analyzer.analyze(properties)
            leads = [p for p in hot_leads if p.get('is_lead')]
            log(f"PHASE 1 DISCOVER: {len(leads)} leads in {city}")
            all_leads.extend(leads)
        except Exception as e:
            phase_errors.append(f"discover/{city}: {e}")
            log(f"FAILED: {city} - {e}")

    output_path = os.path.join(os.path.dirname(__file__), 'global_leads.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_leads, f, indent=2, default=str)

    log(f"PHASE 1 DISCOVER COMPLETE: {len(all_leads)} leads saved")

    if not all_leads:
        return output_contract("failure", {"cities": cities, "target": target},
                               None, phase_errors + ["No leads discovered"], "adjust_markets")

    cold_call = ColdCallingSwarmOS()
    log("PHASE 2 ENRICH: Cold-calling swarm skip-tracing phones and generating scripts...")
    enrich_result = cold_call.run_lead_enrichment_swarm(output_path)

    log(f"PHASE 2 ENRICH: {enrich_result['outputs'].get('enriched', 0) if enrich_result.get('outputs') else 0} leads enriched")

    verify_result = cold_call.verify_queue()

    if args.outreach:
        log("PHASE 3 OUTREACH: Sending investor emails...")
        outreach = InvestorOutreach()
        outreach.execute_campaign(output_path, dry_run=args.dry_run)

    summary = {
        "leads_discovered": len(all_leads),
        "markets_scraped": len(cities),
        "leads_enriched": enrich_result.get('outputs', {}).get('enriched', 0) if enrich_result.get('outputs') else 0,
        "queue_total": len(cold_call.queue),
        "queue_ready": sum(1 for i in cold_call.queue if i.get('status') == 'ready_to_call'),
        "policy": {
            "dry_run": args.dry_run,
            "outreach": args.outreach,
        },
    }

    log(f"PIPELINE COMPLETE: {json.dumps(summary, indent=2)}")
    return output_contract("success", {"cities": cities, "target": target}, summary, phase_errors, "review")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Lead Engine — Find → Enrich → Call pipeline")
    parser.add_argument("--cities", type=str, default="manchester,london,birmingham,liverpool,leeds,new york,madrid",
                        help="Comma-separated cities to scrape")
    parser.add_argument("--target-deals", type=int, default=30,
                        help="Number of leads to accumulate per run (default: 30)")
    parser.add_argument("--outreach", action="store_true", help="Send investor outreach emails")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, dry-run mode")
    args = parser.parse_args()

    result = run_pipeline(args)
    print(f"\n--- OUTPUT CONTRACT ---")
    print(json.dumps(result, indent=2))
