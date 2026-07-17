import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

ARTIFACTS = Path(__file__).resolve().parent.parent / "Artifacts"

BUYER_PREFERENCES = {
    "Cash Buyer": {"target_cities": ["Dallas", "Houston", "Austin", "San Antonio"], "max_distance": 50, "min_equity": 30000, "preferred_signals": ["Code Concern", "Boarding", "Vacant"]},
    "Wholesaler": {"target_cities": ["Dallas", "Fort Worth", "Arlington", "Plano", "Irving", "Garland", "Mesquite"], "max_distance": 100, "min_equity": 10000, "preferred_signals": ["Code Concern", "Rental", "Dumping"]},
    "Investor": {"target_cities": ["Dallas", "Austin", "Charlotte", "Atlanta", "Denver", "Phoenix", "Miami", "Orlando", "Tampa", "Houston"], "max_distance": 200, "min_equity": 50000, "preferred_signals": ["Code Concern", "Vacant", "Boarding"]},
    "Property Investor": {"target_cities": ["Dallas", "Houston", "Austin", "Phoenix", "Denver", "Orlando", "Atlanta"], "max_distance": 100, "min_equity": 25000, "preferred_signals": ["Code Concern"]},
    "Real Estate Solutions": {"target_cities": ["Dallas", "Houston", "Austin", "Atlanta", "Phoenix", "Denver", "Miami", "Tampa"], "max_distance": 150, "min_equity": 20000, "preferred_signals": ["Code Concern", "Rental"]},
    "Holdings": {"target_cities": ["Dallas", "Houston", "Atlanta", "Miami", "Tampa", "Phoenix", "Denver", "Austin"], "max_distance": 200, "min_equity": 100000, "preferred_signals": ["Code Concern"]},
    "Equity Partner": {"target_cities": ["Dallas", "Houston", "Austin", "Charlotte", "Tampa"], "max_distance": 75, "min_equity": 40000, "preferred_signals": ["Code Concern", "Boarding"]},
    "Acquisitions": {"target_cities": ["Dallas", "Houston", "Austin", "Atlanta", "Charlotte", "Tampa", "Denver", "Phoenix", "Orlando", "Miami"], "max_distance": 100, "min_equity": 20000, "preferred_signals": ["Code Concern", "Vacant"]},
    "Capital Partner": {"target_cities": ["Dallas", "Houston", "Austin", "Atlanta", "Charlotte", "Denver", "Phoenix", "Miami", "Orlando", "Tampa"], "max_distance": 200, "min_equity": 75000, "preferred_signals": ["Code Concern"]},
}

DISTRESS_WEIGHTS = {
    "Code Concern": 30,
    "Rental": 25,
    "Boarding": 35,
    "Dumping": 20,
    "Vacant": 40,
}

def load_properties(csv_path: Path) -> List[Dict]:
    if not csv_path.exists():
        print(f"Properties file not found: {csv_path}")
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_buyers(csv_path: Path) -> List[Dict]:
    if not csv_path.exists():
        print(f"Buyers file not found: {csv_path}")
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("Lead_Type", "").strip() == "Buyer Contact"]

def normalize_city(city: str) -> str:
    return city.strip().title().split(",")[0].split(" (")[0]

def score_property_urgency(property_row: Dict) -> int:
    urgency = 0
    signal = (property_row.get("Distress_Signal") or "").lower()
    signal_date = property_row.get("Signal_Date", "")
    if "vacant" in signal:
        urgency += 40
    if "board" in signal:
        urgency += 35
    if "code concern" in signal:
        urgency += 30
    if "rental" in signal:
        urgency += 20
    if "dump" in signal:
        urgency += 15
    if signal_date:
        try:
            dt = datetime.fromisoformat(signal_date.replace("Z", ""))
            days_old = (datetime.now() - dt).days
            if days_old <= 7:
                urgency += 25
            elif days_old <= 30:
                urgency += 15
            elif days_old <= 90:
                urgency += 5
        except ValueError:
            pass
    owner = (property_row.get("Owner_Name") or "").strip()
    if owner and owner not in ("", "ACTION_REQUIRED_SKIP_TRACE", "N/A"):
        urgency += 10
    if property_row.get("Owner_Phone", "").strip() and property_row["Owner_Phone"] not in ("", "ACTION_REQUIRED_SKIP_TRACE"):
        urgency += 10
    return min(urgency, 100)

def match_property_to_category(property_city: str, distress_signal: str, buyer_category: str) -> float:
    prefs = BUYER_PREFERENCES.get(buyer_category)
    if not prefs:
        return 0.0
    score = 0.0
    prop_city = normalize_city(property_city)
    if prop_city in [normalize_city(c) for c in prefs["target_cities"]]:
        score += 40.0
    elif any(prop_city.startswith(c[:4]) for c in prefs["target_cities"]):
        score += 20.0
    signal_lower = (distress_signal or "").lower()
    for preferred in prefs["preferred_signals"]:
        if preferred.lower() in signal_lower:
            score += 30.0
            break
    urgency = score_property_urgency({"Distress_Signal": distress_signal, "Signal_Date": "", "Owner_Name": "", "Owner_Phone": ""})
    score += urgency * 0.3
    return round(min(score, 100.0), 1)

def generate_matches(properties: List[Dict], buyers: List[Dict], min_score: float = 50.0) -> List[Dict]:
    matches = []
    for prop in properties:
        prop_city = prop.get("City", prop.get("Property_Address", "")).strip()
        distress = prop.get("Distress_Signal", "Code Concern")
        urgency = score_property_urgency(prop)
        for buyer in buyers:
            category = buyer.get("Category", "").strip()
            buyer_city = (buyer.get("City") or buyer.get("Property_Address") or "").strip()
            match_pct = match_property_to_category(prop_city, distress, category)
            if match_pct < min_score:
                continue
            matches.append({
                "Property_Address": prop.get("Property_Address", ""),
                "Property_City": prop_city,
                "Distress_Signal": distress,
                "Urgency_Score": urgency,
                "Match_Score": match_pct,
                "Buyer_Company": buyer.get("Entity_Name", ""),
                "Buyer_Contact": buyer.get("Contact_Name", ""),
                "Buyer_Email": buyer.get("Email", ""),
                "Buyer_Phone": buyer.get("Phone", ""),
                "Buyer_Category": category,
                "Buyer_City": buyer_city,
                "Owner_Name": prop.get("Owner_Name", ""),
                "Owner_Phone": prop.get("Owner_Phone", ""),
            })
    matches.sort(key=lambda x: (x["Match_Score"], x["Urgency_Score"]), reverse=True)
    return matches

def main():
    master_csv = ARTIFACTS / "all_leads_master.csv"
    if not master_csv.exists():
        latest_csvs = sorted(ARTIFACTS.glob("ALL_LEADS_*.csv"))
        if not latest_csvs:
            print("No lead files found in Artifacts/")
            return
        master_csv = latest_csvs[-1]
    all_data = load_properties(master_csv)
    buyers = [r for r in all_data if r.get("Lead_Type", "").strip() == "Buyer Contact"]
    properties = [r for r in all_data if r.get("Lead_Type", "").strip() == "Distressed Property"]
    print(f"Loaded {len(buyers)} buyers and {len(properties)} distressed properties")
    if not properties or not buyers:
        print("Need both buyers and properties to match")
        return
    matches = generate_matches(properties, buyers, min_score=50.0)
    output_path = ARTIFACTS / f"matched_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if matches:
            writer = csv.DictWriter(f, fieldnames=matches[0].keys())
            writer.writeheader()
            writer.writerows(matches)
    print(f"Generated {len(matches)} matches -> {output_path.name}")
    top = [m for m in matches if m["Match_Score"] >= 80]
    print(f"  High-priority (>=80%): {len(top)}")
    medium = [m for m in matches if 65 <= m["Match_Score"] < 80]
    print(f"  Medium-priority (65-79%): {len(medium)}")
    if top:
        print("\nTop 5 matches:")
        for m in top[:5]:
            addr = m["Property_Address"][:50] if m["Property_Address"] else "N/A"
            print(f"  [{m['Match_Score']}%] {addr} -> {m['Buyer_Company']} ({m['Buyer_Category']})")

if __name__ == "__main__":
    main()
