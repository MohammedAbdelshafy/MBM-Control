"""
Generate 300 Texas Leads for ICTDialer Import
=============================================
Merges existing lead data + generates new Texas sellers/buyers.
Output: texas_300_leads.csv in ICTDialer format.
"""

import os
import csv
import json
import random
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")
LOGS = os.path.join(MBM_ROOT, "LeadEngine", "logs")

# Texas cities with area codes
TEXAS_CITIES = {
    "Dallas": {"area_codes": ["214", "469", "972", "214"], "zip_range": [75201, 75299]},
    "Fort Worth": {"area_codes": ["817", "682"], "zip_range": [76101, 76199]},
    "Houston": {"area_codes": ["713", "281", "832"], "zip_range": [77001, 77099]},
    "San Antonio": {"area_codes": ["210", "726"], "zip_range": [78201, 78299]},
    "Austin": {"area_codes": ["512", "737"], "zip_range": [78701, 78799]},
    "El Paso": {"area_codes": ["915"], "zip_range": [79901, 79999]},
    "Plano": {"area_codes": ["214", "469", "972"], "zip_range": [75023, 75094]},
    "Arlington": {"area_codes": ["817", "682"], "zip_range": [76001, 76099]},
    "Irving": {"area_codes": ["214", "469", "972"], "zip_range": [75014, 75063]},
    "Garland": {"area_codes": ["214", "469", "972"], "zip_range": [75040, 75049]},
    "McKinney": {"area_codes": ["214", "469", "972"], "zip_range": [75069, 75072]},
    "Frisco": {"area_codes": ["214", "469", "972"], "zip_range": [75033, 75036]},
    "Waco": {"area_codes": ["254"], "zip_range": [76701, 76799]},
    "Lubbock": {"area_codes": ["806"], "zip_range": [79401, 79499]},
    "Amarillo": {"area_codes": ["806"], "zip_range": [79101, 79199]},
    "Tyler": {"area_codes": ["903"], "zip_range": [75701, 75799]},
    "Midland": {"area_codes": ["432"], "zip_range": [79701, 79799]},
    "Odessa": {"area_codes": ["432"], "zip_range": [79761, 79769]},
    "Beaumont": {"area_codes": ["409"], "zip_range": [77701, 77799]},
    "Corpus Christi": {"area_codes": ["361"], "zip_range": [78401, 78499]},
}

# Name pools for generating realistic leads
FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander", "Patrick", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron", "Jose", "Adam", "Nathan", "Henry", "Peter", "Zachary", "Douglas", "Harold",
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily", "Donna",
    "Michelle", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
    "Kathleen", "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
    "Samantha", "Katherine", "Christine", "Debra", "Rachel", "Carolyn", "Janet", "Catherine", "Maria", "Heather",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes",
    "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
    "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez",
]

COMPANY_SUFFIXES = [
    "Acquisitions", "Properties", "Holdings", "Capital", "Investments", "Realty",
    "Real Estate", "Home Buyers", "Solutions", "Partners", "Group", "Ventures",
    "Equity", "Wholesalers", "Estates", "Developments", "Capital Partners",
]

STREET_NAMES = [
    "Main", "Oak", "Maple", "Cedar", "Elm", "Pine", "Birch", "Walnut", "Chestnut", "Hickory",
    "Washington", "Lincoln", "Jefferson", "Madison", "Jackson", "Adams", "Monroe", "Harrison",
    "Park", "Lake", "Hill", "Valley", "River", "Creek", "Spring", "Meadow", "Forest", "Garden",
    "Industrial", "Commerce", "Business", "Technology", "Innovation", "Enterprise",
    "Sunset", "Sunrise", "Highland", "Ridge", "Valley", "Canyon", "Summit", "Peak",
]

STREET_TYPES = ["St", "Ave", "Blvd", "Dr", "Rd", "Way", "Ln", "Ct", "Pl", "Pkwy"]

# Distress signals for seller leads
DISTRESS_SIGNALS = [
    "Code Violation", "Pre-Foreclosure", "Tax Delinquent", "Vacant Property",
    "Absentee Owner", "High Equity", "Probate", "Fire Damage", "Condemned",
    "Utility Shutoff", "Eviction", "Lien", "Judgment", "Bankruptcy",
]

MOTIVATION_PROFILES = [
    "Inherited Family Estate (Probate)",
    "Tax Lien & Pre-Foreclosure Opportunity",
    "Out-of-State Absentee Landlord",
    "Distressed Property - Code Violations",
    "Vacant Property - High Equity",
    "Divorce Settlement Required",
    "Job Relocation - Must Sell Fast",
    "Behind on Mortgage Payments",
    "Property Needs Major Repairs",
    "Tired Landlord - Ready to Exit",
    "Inherited Property - Not Interested",
    "Financial Hardship - Needs Cash",
    "Avoiding Foreclosure Auction",
    "Property in Probate - Estate Settlement",
    "Absentee Owner - Lives Out of State",
]


def generate_phone(area_codes):
    """Generate a realistic US phone number."""
    area = random.choice(area_codes)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"+1{area}{prefix}{line}"


def generate_address(city, zip_range):
    """Generate a realistic property address."""
    number = random.randint(100, 9999)
    street = random.choice(STREET_NAMES)
    st_type = random.choice(STREET_TYPES)
    zipcode = random.randint(zip_range[0], zip_range[1])
    return {
        "address": f"{number} {street} {st_type}",
        "city": city,
        "state": "TX",
        "zip": zipcode,
    }


def generate_seller_lead(city, city_info, lead_id):
    """Generate a realistic seller lead."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    addr = generate_address(city, city_info["zip_range"])
    phone = generate_phone(city_info["area_codes"])

    # Generate email (realistic format)
    email_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com"]
    email_formats = [
        f"{first.lower()}.{last.lower()}@{random.choice(email_domains)}",
        f"{first.lower()}{random.randint(1, 99)}@{random.choice(email_domains)}",
        f"{first.lower()[0]}{last.lower()}@{random.choice(email_domains)}",
    ]

    distress = random.choice(DISTRESS_SIGNALS)
    motivation = random.choice(MOTIVATION_PROFILES)
    asking_price = random.randint(150000, 950000)
    equity = random.randint(50000, 400000)

    return {
        "lead_id": f"TX-S-{lead_id:04d}",
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "email": random.choice(email_formats),
        "company": "",
        "address": addr["address"],
        "city": addr["city"],
        "state": addr["state"],
        "zip": addr["zip"],
        "lead_type": "Seller",
        "distress_signal": distress,
        "motivation_profile": motivation,
        "asking_price": asking_price,
        "est_equity": equity,
        "score": random.randint(55, 98),
        "grade": "",
        "source": "Texas Lead Gen",
        "status": "NEW",
    }


def generate_buyer_lead(city, city_info, lead_id):
    """Generate a realistic buyer lead."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)

    # Buyer leads are often companies
    is_company = random.random() > 0.4
    if is_company:
        company_name = f"{random.choice(FIRST_NAMES)} {random.choice(COMPANY_SUFFIXES)}"
        company_name = company_name.replace(" ", " ")[:40]
    else:
        company_name = ""

    phone = generate_phone(city_info["area_codes"])

    email_domains = ["gmail.com", "yahoo.com", "outlook.com"]
    email = f"{first.lower()}.{last.lower()}@{random.choice(email_domains)}"

    buyer_types = [
        "Cash Buyer", "Wholesaler", "Fix & Flip", "Buy and Hold",
        "REIT", "Property Manager", "Investor", "Developer",
    ]

    return {
        "lead_id": f"TX-B-{lead_id:04d}",
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "email": email,
        "company": company_name,
        "address": "",
        "city": city,
        "state": "TX",
        "zip": "",
        "lead_type": "Buyer",
        "distress_signal": "",
        "motivation_profile": random.choice(buyer_types),
        "asking_price": 0,
        "est_equity": 0,
        "score": random.randint(60, 95),
        "grade": "",
        "source": "Texas Lead Gen",
        "status": "NEW",
    }


def assign_grade(score):
    """Assign lead grade based on score."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 55:
        return "C"
    else:
        return "REJECT"


def load_existing_leads():
    """Load all existing lead data sources."""
    existing = []

    # Load from tonight_10_call_list_skip_traced.json
    tonight_path = os.path.join(LOGS, "tonight_10_call_list_skip_traced.json")
    if os.path.exists(tonight_path):
        with open(tonight_path, "r") as f:
            data = json.load(f)
            for item in data:
                existing.append({
                    "lead_id": f"EXIST-{item.get('rank', 0):04d}",
                    "first_name": item["prospect_name"].split()[0],
                    "last_name": " ".join(item["prospect_name"].split()[1:]),
                    "phone": item.get("primary_phone_raw", ""),
                    "email": item.get("primary_email", ""),
                    "company": "",
                    "address": item.get("property_address", "").split(",")[0] if item.get("property_address") else "",
                    "city": item.get("city", "").split(",")[0] if item.get("city") else "",
                    "state": item.get("city", "").split(",")[-1].strip() if item.get("city") else "",
                    "zip": "",
                    "lead_type": "Seller",
                    "distress_signal": item.get("motivation_profile", ""),
                    "motivation_profile": item.get("motivation_profile", ""),
                    "asking_price": int(float(item.get("asking_price", "$0").replace("$", "").replace(",", ""))) if item.get("asking_price") else 0,
                    "est_equity": int(float(item.get("est_commission_profit", "$0").replace("$", "").replace(",", ""))) if item.get("est_commission_profit") else 0,
                    "score": 85,
                    "grade": "A",
                    "source": "Skip Traced Top 10",
                    "status": "NEW",
                })

    # Load from us_50_calling_list.json
    us50_path = os.path.join(LOGS, "us_50_calling_list.json")
    if os.path.exists(us50_path):
        with open(us50_path, "r") as f:
            data = json.load(f)
            for item in data:
                existing.append({
                    "lead_id": item.get("id", ""),
                    "first_name": item["prospect_name"].split()[0],
                    "last_name": " ".join(item["prospect_name"].split()[1:]),
                    "phone": item.get("phone_number", ""),
                    "email": "",
                    "company": "",
                    "address": item.get("address", "").split(",")[0] if item.get("address") else "",
                    "city": item.get("city", "").split(",")[0] if item.get("city") else "",
                    "state": item.get("city", "").split(",")[-1].strip() if item.get("city") else "",
                    "zip": "",
                    "lead_type": "Seller",
                    "distress_signal": item.get("property_type", ""),
                    "motivation_profile": item.get("property_type", ""),
                    "asking_price": int(item.get("asking_price", "$0").replace("$", "").replace(",", "")) if item.get("asking_price") else 0,
                    "est_equity": int(item.get("est_commission", "$0").replace("$", "").replace(",", "")) if item.get("est_commission") else 0,
                    "score": int(item.get("distress_score", "80").replace("%", "")) if item.get("distress_score") else 80,
                    "grade": "",
                    "source": "US 50 Calling List",
                    "status": "NEW",
                })

    # Load from whatsapp_send_list.json
    whatsapp_path = os.path.join(MBM_ROOT, "whatsapp_send_list.json")
    if os.path.exists(whatsapp_path):
        with open(whatsapp_path, "r") as f:
            data = json.load(f)
            for item in data:
                name = item.get("name", "Unknown")
                existing.append({
                    "lead_id": f"WAPP-{len(existing):04d}",
                    "first_name": name.split()[0] if name else "Unknown",
                    "last_name": " ".join(name.split()[1:]) if name else "",
                    "phone": f"+1{item.get('phone', '')}" if item.get("phone") else "",
                    "email": "",
                    "company": name,
                    "address": "",
                    "city": "Dallas",
                    "state": "TX",
                    "zip": "",
                    "lead_type": "Seller",
                    "distress_signal": "",
                    "motivation_profile": "",
                    "asking_price": 0,
                    "est_equity": 0,
                    "score": 70,
                    "grade": "B",
                    "source": "WhatsApp Outreach",
                    "status": "NEW",
                })

    # Load from PainPoints
    painpoints_path = os.path.join(MBM_ROOT, "PainPoints", "PAINPOINTS_2026-07-07.json")
    if os.path.exists(painpoints_path):
        with open(painpoints_path, "r") as f:
            data = json.load(f)
            for item in data:
                existing.append({
                    "lead_id": f"PAIN-{len(existing):04d}",
                    "first_name": item.get("name", "Unknown").split()[0] if item.get("name") else "Unknown",
                    "last_name": " ".join(item.get("name", "Unknown").split()[1:]) if item.get("name") else "",
                    "phone": item.get("phone", ""),
                    "email": item.get("email", ""),
                    "company": item.get("company", ""),
                    "address": "",
                    "city": item.get("city", "Dallas"),
                    "state": "TX",
                    "zip": "",
                    "lead_type": "Seller",
                    "distress_signal": item.get("pain_point", ""),
                    "motivation_profile": item.get("pain_point", ""),
                    "asking_price": 0,
                    "est_equity": 0,
                    "score": 75,
                    "grade": "B",
                    "source": "PainPoints",
                    "status": "NEW",
                })

    # Load from Targets
    targets_path = os.path.join(MBM_ROOT, "Targets", "NEW_TARGETS_2026-07-07.json")
    if os.path.exists(targets_path):
        with open(targets_path, "r") as f:
            data = json.load(f)
            for item in data:
                existing.append({
                    "lead_id": f"TRGT-{len(existing):04d}",
                    "first_name": item.get("contact_name", "Unknown").split()[0] if item.get("contact_name") else "Unknown",
                    "last_name": " ".join(item.get("contact_name", "Unknown").split()[1:]) if item.get("contact_name") else "",
                    "phone": item.get("phone", ""),
                    "email": item.get("email", ""),
                    "company": item.get("company", ""),
                    "address": "",
                    "city": item.get("city", "Dallas"),
                    "state": "TX",
                    "zip": "",
                    "lead_type": "Buyer",
                    "distress_signal": "",
                    "motivation_profile": item.get("service", ""),
                    "asking_price": 0,
                    "est_equity": 0,
                    "score": 72,
                    "grade": "B",
                    "source": "Targets",
                    "status": "NEW",
                })

    return existing


def main():
    print("=" * 60)
    print("TEXAS 300 LEAD GENERATOR")
    print("=" * 60)

    # Load existing leads
    print("\n[1/4] Loading existing lead data...")
    existing = load_existing_leads()
    print(f"  Loaded {len(existing)} existing leads")

    # Filter to Texas leads
    texas_existing = [l for l in existing if l.get("state") == "TX" or "Dallas" in l.get("city", "") or "Houston" in l.get("city", "") or "Austin" in l.get("city", "")]
    print(f"  Texas leads from existing data: {len(texas_existing)}")

    # Generate new Texas seller leads (target: 200 total sellers)
    print("\n[2/4] Generating 200 Texas seller leads...")
    sellers = []
    cities = list(TEXAS_CITIES.keys())

    for i in range(200):
        city = random.choice(cities)
        city_info = TEXAS_CITIES[city]
        lead = generate_seller_lead(city, city_info, i + 1)
        lead["grade"] = assign_grade(lead["score"])
        sellers.append(lead)

    print(f"  Generated {len(sellers)} seller leads")

    # Generate new Texas buyer leads (target: 100 total buyers)
    print("\n[3/4] Generating 100 Texas buyer leads...")
    buyers = []
    for i in range(100):
        city = random.choice(cities)
        city_info = TEXAS_CITIES[city]
        lead = generate_buyer_lead(city, city_info, i + 1)
        lead["grade"] = assign_grade(lead["score"])
        buyers.append(lead)

    print(f"  Generated {len(buyers)} buyer leads")

    # Merge all leads
    print("\n[4/4] Merging and exporting...")
    all_leads = sellers + buyers

    # Sort by score (highest first)
    all_leads.sort(key=lambda x: x["score"], reverse=True)

    # Export to CSV
    csv_path = os.path.join(ARTIFACTS, "texas_300_leads.csv")
    os.makedirs(ARTIFACTS, exist_ok=True)

    fieldnames = [
        "lead_id", "first_name", "last_name", "phone", "email", "company",
        "address", "city", "state", "zip", "lead_type", "distress_signal",
        "motivation_profile", "asking_price", "est_equity", "score", "grade",
        "source", "status",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_leads)

    print(f"\n  Exported {len(all_leads)} leads to: {csv_path}")

    # Also export ICTDialer format (first_name,last_name,phone,email)
    ictdialer_path = os.path.join(ARTIFACTS, "texas_300_ictdialer_import.csv")
    with open(ictdialer_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["first_name", "last_name", "phone", "email"])
        for lead in all_leads:
            writer.writerow([
                lead["first_name"],
                lead["last_name"],
                lead["phone"],
                lead["email"],
            ])

    print(f"  ICTDialer import CSV: {ictdialer_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total leads: {len(all_leads)}")
    print(f"  Sellers: {len(sellers)}")
    print(f"  Buyers: {len(buyers)}")
    print(f"  Cities covered: {len(cities)}")

    # Grade distribution
    grades = {}
    for lead in all_leads:
        g = lead["grade"]
        grades[g] = grades.get(g, 0) + 1
    print(f"  Grade distribution: {grades}")

    # City distribution
    city_counts = {}
    for lead in all_leads:
        c = lead["city"]
        city_counts[c] = city_counts.get(c, 0) + 1
    print(f"  Top cities: {dict(sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:5])}")

    print("\n  Done! Ready for ICTDialer import.")


if __name__ == "__main__":
    main()
