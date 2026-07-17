import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timezone

ARTIFACTS = Path(__file__).resolve().parent.parent / "Artifacts"
LEAD_PACKS = Path(__file__).resolve().parent.parent / "LeadPacks"
CLIENTS = Path(__file__).resolve().parent.parent / "Clients"

DISTRESS_WEIGHTS = {
    "vacant": 40,
    "boarding": 35,
    "code concern": 30,
    "rental": 20,
    "dumping": 15,
    "condemn": 50,
    "fire": 45,
    "water": 25,
    "unsafe": 35,
    "trash": 10,
    "overgrown": 10,
}

CITY_DEMAND = {
    "dallas": 20,
    "fort worth": 17,
    "arlington": 14,
    "plano": 15,
    "irving": 13,
    "garland": 12,
    "mesquite": 11,
    "carrollton": 13,
    "frisco": 16,
    "mckinney": 14,
    "allen": 13,
    "richardson": 12,
    "addison": 11,
    "coppell": 11,
    "lewisville": 10,
    "denton": 12,
    "flower mound": 11,
    "grapevine": 12,
    "southlake": 13,
}

def score_property(prop: Dict) -> Tuple[int, Dict[str, int]]:
    breakdown = {}
    total = 0
    signal = (prop.get("Distress_Signal") or "").lower()
    signal_max = 0
    for keyword, weight in DISTRESS_WEIGHTS.items():
        if keyword in signal:
            signal_max = max(signal_max, weight)
    total += signal_max
    breakdown["distress"] = signal_max
    signal_date = prop.get("Signal_Date", "")
    recency = 0
    if signal_date:
        try:
            dt = datetime.fromisoformat(signal_date.replace("Z", "").replace("+00:00", ""))
            days_old = (datetime.now() - dt).days if dt.tzinfo is None else (datetime.now(timezone.utc) - dt).days
            if days_old <= 3:
                recency = 30
            elif days_old <= 7:
                recency = 25
            elif days_old <= 14:
                recency = 20
            elif days_old <= 30:
                recency = 15
            elif days_old <= 60:
                recency = 10
            elif days_old <= 90:
                recency = 5
        except ValueError:
            pass
    total += recency
    breakdown["recency"] = recency
    owner_name = (prop.get("Owner_Name") or "").strip()
    owner_phone = (prop.get("Owner_Phone") or "").strip()
    contact_completeness = 0
    if owner_name and owner_name not in ("ACTION_REQUIRED_SKIP_TRACE", "N/A", ""):
        contact_completeness += 15
        breakdown["has_owner_name"] = 15
    if owner_phone and owner_phone not in ("ACTION_REQUIRED_SKIP_TRACE", "N/A", ""):
        contact_completeness += 15
        breakdown["has_owner_phone"] = 15
    total += contact_completeness
    address = (prop.get("Property_Address") or "").lower()
    city_score = 0
    for city_name, demand in CITY_DEMAND.items():
        if city_name in address:
            city_score = demand
            break
    total += city_score
    breakdown["city_demand"] = city_score
    owner_city = (prop.get("City") or "").strip().lower()
    if owner_city and owner_city not in ("", "action_required_skip_trace") and city_score == 0:
        city_score = CITY_DEMAND.get(owner_city, 5)
        total += city_score
        breakdown["city_demand"] = city_score
    total = min(total, 100)
    breakdown["total"] = total
    return total, breakdown

PRIORITY_MAP = {90: "CRITICAL", 75: "HIGH", 60: "MEDIUM", 0: "LOW"}

def get_priority(score: int) -> str:
    for threshold, label in sorted(PRIORITY_MAP.items(), reverse=True):
        if score >= threshold:
            return label
    return "LOW"

def recommend_action(prop: Dict, score: int, priority: str) -> str:
    actions = []
    owner_phone = (prop.get("Owner_Phone") or "").strip()
    owner_name = (prop.get("Owner_Name") or "").strip()
    if not owner_phone or owner_phone in ("ACTION_REQUIRED_SKIP_TRACE", "", "N/A"):
        actions.append("SKIP_TRACE")
    if not owner_name or owner_name in ("ACTION_REQUIRED_SKIP_TRACE", "", "N/A"):
        actions.append("FIND_OWNER")
    if score >= 75:
        actions.append("PRIORITY_OUTREACH")
    actions.append("LOG_TO_PIPELINE")
    return " | ".join(actions)

def load_leads(csv_paths: List[Path]) -> List[Dict]:
    all_leads = []
    seen = set()
    for p in csv_paths:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                addr = (row.get("Property_Address") or row.get("address") or "").strip().lower()
                if addr and addr not in seen:
                    seen.add(addr)
                    all_leads.append(row)
    return all_leads

def main():
    sources = sorted(ARTIFACTS.glob("raw_leads_Dallas_311_*.csv")) + sorted(ARTIFACTS.glob("ALL_LEADS_*.csv"))
    master = ARTIFACTS / "all_leads_master.csv"
    if master.exists():
        sources.insert(0, master)
    if not sources:
        print("No lead files found")
        return
    props = load_leads(sources)
    props = [p for p in props if "Lead_Type" not in p or p.get("Lead_Type", "").strip() == "Distressed Property"]
    if not props:
        props = load_leads(sources)
    print(f"Scoring {len(props)} properties")
    scored = []
    for p in props:
        score, breakdown = score_property(p)
        priority = get_priority(score)
        action = recommend_action(p, score, priority)
        address = p.get("Property_Address", p.get("address", ""))
        city = p.get("City", "")
        signal = p.get("Distress_Signal", p.get("subject", ""))
        scored.append({
            "Priority": priority,
            "Score": score,
            "Property_Address": address,
            "City": city,
            "Distress_Signal": signal,
            "Signal_Date": p.get("Signal_Date", p.get("created_date", "")),
            "Owner_Name": p.get("Owner_Name", ""),
            "Owner_Phone": p.get("Owner_Phone", ""),
            "Recommended_Actions": action,
            "Breakdown": json.dumps(breakdown),
        })
    scored.sort(key=lambda x: (x["Score"], x.get("Signal_Date", "")), reverse=True)
    output_path = ARTIFACTS / f"scored_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if scored:
            writer = csv.DictWriter(f, fieldnames=scored[0].keys())
            writer.writeheader()
            writer.writerows(scored)
    critical = [s for s in scored if s["Priority"] == "CRITICAL"]
    high = [s for s in scored if s["Priority"] == "HIGH"]
    medium = [s for s in scored if s["Priority"] == "MEDIUM"]
    print(f"Scored -> {output_path.name}")
    print(f"  CRITICAL (90+):  {len(critical)}")
    print(f"  HIGH (75-89):    {len(high)}")
    print(f"  MEDIUM (60-74):  {len(medium)}")
    print(f"  LOW (<60):       {len(scored) - len(critical) - len(high) - len(medium)}")
    if critical:
        print("\nCritical leads — take action now:")
        for s in critical[:5]:
            print(f"  [{s['Score']}] {s['Property_Address'][:50]} | {s['Distress_Signal'][:30]} | {s['Recommended_Actions']}")
    if high:
        print(f"\nHigh priority — next outreach batch: {len(high)} leads")
        for s in high[:3]:
            print(f"  [{s['Score']}] {s['Property_Address'][:50]} | {s['Distress_Signal'][:30]}")

if __name__ == "__main__":
    main()
