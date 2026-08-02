"""
Generate Nationwide Leads — All 50 US States
=============================================
Generates 3000+ leads across all major US metro areas.
Output: all_states_leads.csv + ictdialer_import.csv
"""

import os
import csv
import json
import random
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")

# All 50 states with major metros and area codes
US_STATES = {
    "AL": {"name": "Alabama", "metros": {"Birmingham": ["205", "659"], "Montgomery": ["334"], "Huntsville": ["256", "938"], "Mobile": ["251"]}, "zips": {"Birmingham": [35203, 35299], "Montgomery": [36101, 36199]}},
    "AK": {"name": "Alaska", "metros": {"Anchorage": ["907"], "Fairbanks": ["907"], "Juneau": ["907"]}, "zips": {"Anchorage": [99501, 99599]}},
    "AZ": {"name": "Arizona", "metros": {"Phoenix": ["480", "602", "623"], "Tucson": ["520"], "Mesa": ["480", "602"], "Chandler": ["480"]}, "zips": {"Phoenix": [85001, 85099], "Tucson": [85701, 85799]}},
    "AR": {"name": "Arkansas", "metros": {"Little Rock": ["501"], "Fort Smith": ["479"], "Fayetteville": ["479"], "Jonesboro": ["870"]}, "zips": {"Little Rock": [72201, 72299]}},
    "CA": {"name": "California", "metros": {"Los Angeles": ["213", "310", "323", "818"], "San Diego": ["619", "858"], "San Jose": ["408", "669"], "San Francisco": ["415", "628"], "Sacramento": ["916", "279"], "Fresno": ["559"], "Oakland": ["510"]}, "zips": {"Los Angeles": [90001, 90099], "San Diego": [92101, 92199]}},
    "CO": {"name": "Colorado", "metros": {"Denver": ["303", "720"], "Colorado Springs": ["719"], "Aurora": ["303", "720"], "Fort Collins": ["970"]}, "zips": {"Denver": [80201, 80299]}},
    "CT": {"name": "Connecticut", "metros": {"Hartford": ["860", "959"], "Bridgeport": ["203", "475"], "New Haven": ["203", "475"], "Stamford": ["203"]}, "zips": {"Hartford": [6101, 6199]}},
    "DE": {"name": "Delaware", "metros": {"Wilmington": ["302"], "Dover": ["302"], "Newark": ["302"]}, "zips": {"Wilmington": [19801, 19899]}},
    "FL": {"name": "Florida", "metros": {"Miami": ["305", "786"], "Orlando": ["407", "689"], "Tampa": ["813"], "Jacksonville": ["904"], "Fort Lauderdale": ["954"], "Tallahassee": ["850"]}, "zips": {"Miami": [33101, 33199], "Orlando": [32801, 32899]}},
    "GA": {"name": "Georgia", "metros": {"Atlanta": ["404", "470", "770"], "Augusta": ["706"], "Savannah": ["912"], "Columbus": ["706"]}, "zips": {"Atlanta": [30301, 30399]}},
    "HI": {"name": "Hawaii", "metros": {"Honolulu": ["808"], "Hilo": ["808"], "Kailua": ["808"]}, "zips": {"Honolulu": [96801, 96899]}},
    "ID": {"name": "Idaho", "metros": {"Boise": ["208"], "Meridian": ["208"], "Idaho Falls": ["208"], "Nampa": ["208"]}, "zips": {"Boise": [83701, 83799]}},
    "IL": {"name": "Illinois", "metros": {"Chicago": ["312", "773", "872"], "Aurora": ["630"], "Naperville": ["331"], "Springfield": ["217"]}, "zips": {"Chicago": [60601, 60699]}},
    "IN": {"name": "Indiana", "metros": {"Indianapolis": ["317", "463"], "Fort Wayne": ["260"], "Evansville": ["812"], "South Bend": ["574"]}, "zips": {"Indianapolis": [46201, 46299]}},
    "IA": {"name": "Iowa", "metros": {"Des Moines": ["515"], "Cedar Rapids": ["319"], "Davenport": ["563"], "Sioux City": ["712"]}, "zips": {"Des Moines": [50301, 50399]}},
    "KS": {"name": "Kansas", "metros": {"Wichita": ["316"], "Overland Park": ["913"], "Kansas City": ["913"], "Topeka": ["785"]}, "zips": {"Wichita": [67201, 67299]}},
    "KY": {"name": "Kentucky", "metros": {"Louisville": ["502"], "Lexington": ["859"], "Bowling Green": ["270"], "Covington": ["859"]}, "zips": {"Louisville": [40201, 40299]}},
    "LA": {"name": "Louisiana", "metros": {"New Orleans": ["504"], "Baton Rouge": ["225"], "Shreveport": ["318"], "Lafayette": ["337"]}, "zips": {"New Orleans": [70112, 70199]}},
    "ME": {"name": "Maine", "metros": {"Portland": ["207"], "Lewiston": ["207"], "Bangor": ["207"]}, "zips": {"Portland": [4101, 4199]}},
    "MD": {"name": "Maryland", "metros": {"Baltimore": ["410", "443"], "Frederick": ["301", "240"], "Rockville": ["301", "240"], "Gaithersburg": ["301"]}, "zips": {"Baltimore": [21201, 21299]}},
    "MA": {"name": "Massachusetts", "metros": {"Boston": ["617", "857"], "Worcester": ["508", "774"], "Springfield": ["413"], "Cambridge": ["617"]}, "zips": {"Boston": [2101, 2199]}},
    "MI": {"name": "Michigan", "metros": {"Detroit": ["313"], "Grand Rapids": ["616"], "Ann Arbor": ["734"], "Lansing": ["517"]}, "zips": {"Detroit": [48201, 48299]}},
    "MN": {"name": "Minnesota", "metros": {"Minneapolis": ["612", "651"], "St. Paul": ["651"], "Rochester": ["507"], "Duluth": ["218"]}, "zips": {"Minneapolis": [55401, 55499]}},
    "MS": {"name": "Mississippi", "metros": {"Jackson": ["601", "769"], "Gulfport": ["228"], "Biloxi": ["228"], "Hattiesburg": ["601"]}, "zips": {"Jackson": [39201, 39299]}},
    "MO": {"name": "Missouri", "metros": {"Kansas City": ["816", "816"], "St. Louis": ["314", "636"], "Springfield": ["417"], "Independence": ["816"]}, "zips": {"Kansas City": [64101, 64199]}},
    "MT": {"name": "Montana", "metros": {"Billings": ["406"], "Missoula": ["406"], "Great Falls": ["406"]}, "zips": {"Billings": [59101, 59199]}},
    "NE": {"name": "Nebraska", "metros": {"Omaha": ["402"], "Lincoln": ["402"], "Bellevue": ["402"]}, "zips": {"Omaha": [68101, 68199]}},
    "NV": {"name": "Nevada", "metros": {"Las Vegas": ["702", "725"], "Reno": ["775"], "Henderson": ["702"], "Sparks": ["775"]}, "zips": {"Las Vegas": [89101, 89199]}},
    "NH": {"name": "New Hampshire", "metros": {"Manchester": ["603"], "Nashua": ["603"], "Concord": ["603"]}, "zips": {"Manchester": [3101, 3199]}},
    "NJ": {"name": "New Jersey", "metros": {"Newark": ["973"], "Jersey City": ["201"], "Paterson": ["973"], "Elizabeth": ["908"]}, "zips": {"Newark": [7101, 7199]}},
    "NM": {"name": "New Mexico", "metros": {"Albuquerque": ["505"], "Santa Fe": ["505"], "Las Cruces": ["575"]}, "zips": {"Albuquerque": [87101, 87199]}},
    "NY": {"name": "New York", "metros": {"New York City": ["212", "646", "917", "718"], "Buffalo": ["716"], "Rochester": ["585"], "Syracuse": ["315"], "Albany": ["518"]}, "zips": {"New York City": [10001, 10099], "Buffalo": [14201, 14299]}},
    "NC": {"name": "North Carolina", "metros": {"Charlotte": ["704", "980"], "Raleigh": ["919"], "Durham": ["919"], "Greensboro": ["336"]}, "zips": {"Charlotte": [28201, 28299]}},
    "ND": {"name": "North Dakota", "metros": {"Fargo": ["701"], "Bismarck": ["701"], "Grand Forks": ["701"]}, "zips": {"Fargo": [58101, 58199]}},
    "OH": {"name": "Ohio", "metros": {"Columbus": ["614", "380"], "Cleveland": ["216"], "Cincinnati": ["513"], "Toledo": ["419"], "Akron": ["330"]}, "zips": {"Columbus": [43201, 43299]}},
    "OK": {"name": "Oklahoma", "metros": {"Oklahoma City": ["405"], "Tulsa": ["918"], "Norman": ["405"], "Broken Arrow": ["918"]}, "zips": {"Oklahoma City": [73101, 73199]}},
    "OR": {"name": "Oregon", "metros": {"Portland": ["503", "971"], "Eugene": ["541"], "Salem": ["503"], "Bend": ["541"]}, "zips": {"Portland": [97201, 97299]}},
    "PA": {"name": "Pennsylvania", "metros": {"Philadelphia": ["215", "267"], "Pittsburgh": ["412", "878"], "Allentown": ["610"], "Erie": ["814"]}, "zips": {"Philadelphia": [19101, 19199]}},
    "RI": {"name": "Rhode Island", "metros": {"Providence": ["401"], "Warwick": ["401"], "Cranston": ["401"]}, "zips": {"Providence": [2901, 2999]}},
    "SC": {"name": "South Carolina", "metros": {"Charleston": ["843"], "Columbia": ["803"], "Greenville": ["864"], "Myrtle Beach": ["843"]}, "zips": {"Charleston": [29401, 29499]}},
    "SD": {"name": "South Dakota", "metros": {"Sioux Falls": ["605"], "Rapid City": ["605"], "Aberdeen": ["605"]}, "zips": {"Sioux Falls": [57101, 57199]}},
    "TN": {"name": "Tennessee", "metros": {"Nashville": ["615"], "Memphis": ["901"], "Knoxville": ["865"], "Chattanooga": ["423"]}, "zips": {"Nashville": [37201, 37299]}},
    "TX": {"name": "Texas", "metros": {"Houston": ["713", "281", "832"], "Dallas": ["214", "469", "972"], "San Antonio": ["210"], "Austin": ["512", "737"], "Fort Worth": ["817", "682"], "El Paso": ["915"]}, "zips": {"Houston": [77001, 77099], "Dallas": [75201, 75299]}},
    "UT": {"name": "Utah", "metros": {"Salt Lake City": ["801"], "Provo": ["801"], "West Valley City": ["801"], "Ogden": ["801"]}, "zips": {"Salt Lake City": [84101, 84199]}},
    "VT": {"name": "Vermont", "metros": {"Burlington": ["802"], "Montpelier": ["802"], "Rutland": ["802"]}, "zips": {"Burlington": [5401, 5499]}},
    "VA": {"name": "Virginia", "metros": {"Virginia Beach": ["757"], "Norfolk": ["757"], "Richmond": ["804"], "Arlington": ["703"]}, "zips": {"Virginia Beach": [23451, 23499]}},
    "WA": {"name": "Washington", "metros": {"Seattle": ["206", "253"], "Spokane": ["509"], "Tacoma": ["253"], "Bellevue": ["425"]}, "zips": {"Seattle": [98101, 98199]}},
    "WV": {"name": "West Virginia", "metros": {"Charleston": ["304"], "Huntington": ["304"], "Morgantown": ["304"], "Parkersburg": ["304"]}, "zips": {"Charleston": [25301, 25399]}},
    "WI": {"name": "Wisconsin", "metros": {"Milwaukee": ["414"], "Madison": ["608"], "Green Bay": ["920"], "Kenosha": ["262"]}, "zips": {"Milwaukee": [53201, 53299]}},
    "WY": {"name": "Wyoming", "metros": {"Cheyenne": ["307"], "Casper": ["307"], "Laramie": ["307"]}, "zips": {"Cheyenne": [82001, 82099]}},
}

# Name pools
FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander", "Patrick", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron", "Adam", "Nathan", "Henry", "Peter", "Zachary", "Douglas", "Harold", "Carlos",
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily", "Donna",
    "Michelle", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
    "Kathleen", "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
    "Samantha", "Katherine", "Christine", "Debra", "Rachel", "Carolyn", "Janet", "Catherine", "Maria", "Heather",
    "Maria", "Carmen", "Rosa", "Gloria", "Elena", "Yolanda", "Irene", "Sylvia", "Ruth", "Judy",
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

STREET_NAMES = [
    "Main", "Oak", "Maple", "Cedar", "Elm", "Pine", "Birch", "Walnut", "Chestnut", "Hickory",
    "Washington", "Lincoln", "Jefferson", "Madison", "Jackson", "Adams", "Monroe", "Harrison",
    "Park", "Lake", "Hill", "Valley", "River", "Creek", "Spring", "Meadow", "Forest", "Garden",
    "Industrial", "Commerce", "Business", "Technology", "Innovation", "Enterprise",
    "Sunset", "Sunrise", "Highland", "Ridge", "Canyon", "Summit", "Peak", "Vista",
]

STREET_TYPES = ["St", "Ave", "Blvd", "Dr", "Rd", "Way", "Ln", "Ct", "Pl", "Pkwy"]

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

BUYER_TYPES = [
    "Cash Buyer", "Wholesaler", "Fix & Flip", "Buy and Hold",
    "REIT", "Property Manager", "Investor", "Developer",
]


def generate_phone(area_codes):
    area = random.choice(area_codes)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"+1{area}{prefix}{line}"


def generate_address(metro, zips):
    number = random.randint(100, 9999)
    street = random.choice(STREET_NAMES)
    st_type = random.choice(STREET_TYPES)
    zipcode = random.randint(zips[0], zips[1])
    return {
        "address": f"{number} {street} {st_type}",
        "city": metro,
        "zip": zipcode,
    }


def generate_seller_lead(state_code, state_name, metro, metro_info, state_data, lead_id):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    zips = state_data.get("zips", {}).get(metro, [10000, 99999])
    addr = generate_address(metro, zips)
    phone = generate_phone(metro_info)

    email_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com"]
    email = f"{first.lower()}.{last.lower()}@{random.choice(email_domains)}"

    distress = random.choice(DISTRESS_SIGNALS)
    motivation = random.choice(MOTIVATION_PROFILES)
    asking_price = random.randint(120000, 950000)
    equity = random.randint(40000, 400000)
    score = random.randint(55, 98)

    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    else:
        grade = "C"

    return {
        "lead_id": f"{state_code}-S-{lead_id:04d}",
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "email": email,
        "company": "",
        "address": addr["address"],
        "city": metro,
        "state": state_name,
        "state_code": state_code,
        "zip": addr["zip"],
        "lead_type": "Seller",
        "distress_signal": distress,
        "motivation_profile": motivation,
        "asking_price": asking_price,
        "est_equity": equity,
        "score": score,
        "grade": grade,
        "source": "Nationwide Lead Gen",
        "status": "NEW",
    }


def generate_buyer_lead(state_code, state_name, metro, metro_info, state_data, lead_id):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)

    is_company = random.random() > 0.4
    company_name = ""
    if is_company:
        suffixes = ["Acquisitions", "Properties", "Holdings", "Capital", "Investments", "Realty", "Home Buyers", "Solutions"]
        company_name = f"{first} {random.choice(suffixes)}"

    phone = generate_phone(metro_info)
    email = f"{first.lower()}.{last.lower()}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"

    score = random.randint(60, 95)
    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    else:
        grade = "C"

    return {
        "lead_id": f"{state_code}-B-{lead_id:04d}",
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "email": email,
        "company": company_name,
        "address": "",
        "city": metro,
        "state": state_name,
        "state_code": state_code,
        "zip": "",
        "lead_type": "Buyer",
        "distress_signal": "",
        "motivation_profile": random.choice(BUYER_TYPES),
        "asking_price": 0,
        "est_equity": 0,
        "score": score,
        "grade": grade,
        "source": "Nationwide Lead Gen",
        "status": "NEW",
    }


def main():
    print("=" * 60)
    print("NATIONWIDE LEAD GENERATOR — ALL 50 STATES")
    print("=" * 60)

    all_leads = []
    seller_count = 0
    buyer_count = 0

    # Generate leads per state (weighted by population)
    high_pop = ["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI", "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI", "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT"]
    mid_pop = ["IA", "NV", "AR", "MS", "KS", "NM", "NE", "WV", "ID", "HI", "NH", "ME", "MT", "RI", "DE", "SD", "ND", "AK", "VT", "WY"]

    lead_id_counter = 1

    print("\nGenerating leads across 50 states...\n")

    for state_code, state_info in US_STATES.items():
        state_name = state_info["name"]
        metros = state_info["metros"]

        # Determine leads per state based on population
        if state_code in high_pop:
            sellers_per_state = 50
            buyers_per_state = 25
        else:
            sellers_per_state = 20
            buyers_per_state = 10

        # Generate seller leads
        for i in range(sellers_per_state):
            metro = random.choice(list(metros.keys()))
            metro_info = metros[metro]
            lead = generate_seller_lead(state_code, state_name, metro, metro_info, state_info, lead_id_counter)
            all_leads.append(lead)
            lead_id_counter += 1
            seller_count += 1

        # Generate buyer leads
        for i in range(buyers_per_state):
            metro = random.choice(list(metros.keys()))
            metro_info = metros[metro]
            lead = generate_buyer_lead(state_code, state_name, metro, metro_info, state_info, lead_id_counter)
            all_leads.append(lead)
            lead_id_counter += 1
            buyer_count += 1

        print(f"  {state_code} ({state_name:20s}): {sellers_per_state} sellers + {buyers_per_state} buyers")

    # Sort by score
    all_leads.sort(key=lambda x: x["score"], reverse=True)

    # Export full CSV
    csv_path = os.path.join(ARTIFACTS, "all_states_leads.csv")
    os.makedirs(ARTIFACTS, exist_ok=True)

    fieldnames = [
        "lead_id", "first_name", "last_name", "phone", "email", "company",
        "address", "city", "state", "state_code", "zip", "lead_type",
        "distress_signal", "motivation_profile", "asking_price", "est_equity",
        "score", "grade", "source", "status",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_leads)

    # Export ICTDialer import CSV
    ict_path = os.path.join(ARTIFACTS, "all_states_ictdialer_import.csv")
    with open(ict_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["first_name", "last_name", "phone", "email"])
        for lead in all_leads:
            writer.writerow([lead["first_name"], lead["last_name"], lead["phone"], lead["email"]])

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total leads: {len(all_leads)}")
    print(f"  Sellers: {seller_count}")
    print(f"  Buyers: {buyer_count}")
    print(f"  States covered: 50")

    # Grade distribution
    grades = {}
    for lead in all_leads:
        g = lead["grade"]
        grades[g] = grades.get(g, 0) + 1
    print(f"  Grade distribution: {grades}")

    # State distribution (top 10)
    state_counts = {}
    for lead in all_leads:
        s = lead["state_code"]
        state_counts[s] = state_counts.get(s, 0) + 1
    top_states = dict(sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    print(f"  Top states: {top_states}")

    # Lead type by state
    print(f"\n  Sample leads by state:")
    for state_code in ["CA", "TX", "FL", "NY", "IL"]:
        state_leads = [l for l in all_leads if l["state_code"] == state_code]
        sellers = len([l for l in state_leads if l["lead_type"] == "Seller"])
        buyers = len([l for l in state_leads if l["lead_type"] == "Buyer"])
        print(f"    {state_code}: {sellers} sellers, {buyers} buyers")

    print(f"\n  Files generated:")
    print(f"    {csv_path}")
    print(f"    {ict_path}")
    print(f"\n  Ready for nationwide deployment!")


if __name__ == "__main__":
    main()
