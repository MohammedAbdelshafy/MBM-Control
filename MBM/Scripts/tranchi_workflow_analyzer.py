import os
import json
import csv
import glob
from datetime import datetime
import re

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS_DIR = os.path.join(MBM_ROOT, "Artifacts")

def parse_currency(val):
    if not val or val == "Unknown":
        return 0.0
    try:
        clean = re.sub(r'[^\d.]', '', val)
        return float(clean)
    except:
        return 0.0

def calculate_mao(arv):
    """
    Tranchi AI Principle: Calculate Maximum Allowable Offer (MAO).
    Formula: (ARV * 0.70) - Estimated Repairs
    Here we estimate repairs conservatively at 10% of ARV for unseen auction properties.
    """
    estimated_repairs = arv * 0.10
    return (arv * 0.70) - estimated_repairs

def analyze_auction_leads():
    print("[*] Running Tranchi AI Workflow Analyzer on Auction Leads...")
    
    # Find latest auction leads file
    auction_files = sorted(glob.glob(os.path.join(ARTIFACTS_DIR, "auction_leads_*.csv")), reverse=True)
    if not auction_files:
        print("[-] No auction leads found to analyze.")
        return
        
    latest_file = auction_files[0]
    print(f"[*] Analyzing {os.path.basename(latest_file)}")
    
    analyzed_properties = []
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            arv = parse_currency(row.get('Estimated_Value', '0'))
            starting_bid = parse_currency(row.get('Starting_Bid', '0'))
            
            if arv > 0:
                mao = calculate_mao(arv)
                
                # Deal structuring logic
                if starting_bid < mao:
                    tier = "Tier A"
                    deal_notes = f"High Potential: Starting bid (${starting_bid:,.2f}) is below MAO (${mao:,.2f}). Target flip margin > 20%."
                elif starting_bid < (arv * 0.85):
                    tier = "Tier B"
                    deal_notes = f"Moderate Potential: Bid is above MAO but below 85% ARV. Needs creative financing or tight rehab."
                else:
                    tier = "Tier C"
                    deal_notes = f"Low Potential: Starting bid is too close to ARV."
                    
                row['Calculated_MAO'] = f"${mao:,.2f}"
                row['Deal_Tier'] = tier
                row['Tranchi_Analysis'] = deal_notes
            else:
                row['Calculated_MAO'] = "Unknown"
                row['Deal_Tier'] = "Unknown"
                row['Tranchi_Analysis'] = "Insufficient data to calculate MAO."
                
            analyzed_properties.append(row)
            
    if analyzed_properties:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(ARTIFACTS_DIR, f"tranchi_analyzed_{timestamp}.csv")
        
        fieldnames = list(analyzed_properties[0].keys())
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(analyzed_properties)
            
        print(f"[+] Tranchi analysis complete. Saved {len(analyzed_properties)} structured deals to {output_file}")
        
if __name__ == "__main__":
    analyze_auction_leads()
