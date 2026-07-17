import csv
import os
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")

# Real wholesalers found from web research (RealEstateBees, HouseCashin, KeyCrew, BiggerPockets)
NEW_WHOLESALERS = [
    # RealEstateBees - Top Dallas Wholesalers
    {"Company": "Preferred Luxury Rentals & Equity", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Multi-state wholesaler"},
    {"Company": "Turner & Partners, LLC", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "100+ assignments since 2020, multi-family + wholesale"},
    {"Company": "AirBorn Estate, LLC", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "Darren Brown", "Email": "", "Phone": "813-683-2574", "Notes": "EquityFlow Real Estate Solutions"},
    {"Company": "Big Stepper Investor", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Wholesaler"},
    {"Company": "Leal Enterprises, LLC", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "Zarek Scott Leal", "Email": "", "Phone": "", "Notes": "Managing Partner, off-market deals"},
    {"Company": "Mindful Investors", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Southern states focus"},
    {"Company": "Wholesale Tank", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Partners with wholesalers, funds EMD"},
    {"Company": "CDL Holdings", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "RealEstateBees", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Wholesale and fix and flip"},

    # HouseCashin - Dallas Wholesalers
    {"Company": "Ali Abtin", "Website": "https://housecashin.com/directory/real-estate-wholesalers/dallas-tx/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "Ali Abtin", "Email": "", "Phone": "", "Notes": "Top wholesaler"},
    {"Company": "Niko Martillo", "Website": "https://housecashin.com/directory/real-estate-wholesalers/dallas-tx/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "Niko Martillo", "Email": "", "Phone": "", "Notes": "Top wholesaler"},
    {"Company": "Shanesse Roye", "Website": "https://housecashin.com/directory/real-estate-wholesalers/dallas-tx/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "Shanesse Roye", "Email": "", "Phone": "", "Notes": "Top wholesaler"},
    {"Company": "VeriServe Solutions", "Website": "https://housecashin.com/directory/real-estate-wholesalers/dallas-tx/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Top wholesaler"},
    {"Company": "Hadid Muhammad", "Website": "https://housecashin.com/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "Hadid Muhammad", "Email": "", "Phone": "", "Notes": "Wholesaler"},
    {"Company": "Veltrin Realty", "Website": "https://housecashin.com/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Wholesaler"},
    {"Company": "Stephanie Houten", "Website": "https://housecashin.com/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "HouseCashin", "Contact_Name": "Stephanie Houten", "Email": "", "Phone": "", "Notes": "Wholesaler"},

    # KeyCrew - Dallas Wholesalers
    {"Company": "New Western", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Largest private source of distressed properties, 250K+ investors"},
    {"Company": "Swift Home Solutions", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW + San Antonio, buys houses any condition"},
    {"Company": "No Worries Home Sale", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Foreclosure, divorce, inherited properties"},
    {"Company": "We Buy Houses Fast in Dallas", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Residential, multi-family, commercial"},
    {"Company": "Fliplist.com", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Off-market investment properties marketplace"},
    {"Company": "Ezer", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Cash offers, flexible closing"},
    {"Company": "Valper Investments", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW + surrounding Texas areas"},
    {"Company": "AO Investments Group", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Since 2012, FL/TX/GA, 1000+ properties"},
    {"Company": "MyHouseDeals", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "National platform, 30+ states, 20-50% below retail"},
    {"Company": "LUSH Property Solutions", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW + Fort Worth, wholesale + fix-and-flip"},
    {"Company": "Easy Offer DFW", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Cash buyer DFW"},

    # BiggerPockets - Active Dallas Wholesalers
    {"Company": "PipHouse LLC", "Website": "https://www.biggerpockets.com/forums/93/topics/1281875", "City": "Dallas, TX", "Lead_Source": "BiggerPockets", "Contact_Name": "Mark", "Email": "", "Phone": "", "Notes": "Active DFW wholesaler, pre-foreclosure + probate + tax delinquent"},

    # BatchLeads / PropStream Sources
    {"Company": "Realestatebees", "Website": "https://realestatebees.com/resources/wholesalers/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Directory of wholesalers"},
    {"Company": "Housecashin", "Website": "https://housecashin.com/directory/real-estate-wholesalers/dallas-tx/", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "102+ wholesale companies in Dallas"},
    {"Company": "Keycrew", "Website": "https://keycrew.co/providers/real-estate-wholesaler/tx/dallas/", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Verified wholesalers directory"},
    {"Company": "FlipMantis", "Website": "https://flipmantis.com/wholesaling/dallas", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Lead generation platform for wholesalers"},
    {"Company": "Reivesti", "Website": "https://www.reivesti.com/dallas-tx-wholesale-real-estate/", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "#1 wholesale source Dallas + Tarrant County"},
    {"Company": "GrizzlyLeads", "Website": "https://grizzlyleads.com/real-estate-leads/Dallas_TX", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Buyer and seller leads platform"},
    {"Company": "Dallas Cash Home Buyers", "Website": "https://dallascashhomebuyers.com/", "City": "Dallas, TX", "Lead_Source": "BatchLeads/PropStream", "Contact_Name": "", "Email": "", "Phone": "469-728-8664", "Notes": "5751 Arlington Park Dr, buys houses any condition"},

    # Facebook Groups - DFW Wholesalers
    {"Company": "DFW Wholesale Investment Real Estate (Group)", "Website": "https://www.facebook.com/groups/942846812392787/", "City": "Dallas, TX", "Lead_Source": "Facebook Group", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Active DFW wholesale deals group"},
    {"Company": "Texas Wholesale Real Estate (Group)", "Website": "https://www.facebook.com/groups/372162476811879/", "City": "Texas", "Lead_Source": "Facebook Group", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "State-wide wholesale deals group"},
    {"Company": "Real Estate Investor & Wholesale Club (Group)", "Website": "https://www.facebook.com/groups/REinvestorwholesaleclub/", "City": "San Antonio/Austin, TX", "Lead_Source": "Facebook Group", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "SA, Austin investor club"},
    {"Company": "DFW Investment/wholesale Properties (ConnectedInvestors)", "Website": "https://connectedinvestors.com/forum/group/dfw-investment-wholesale-properties", "City": "Dallas, TX", "Lead_Source": "Facebook/ConnectedInvestors", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW investment/wholesale properties forum"},
    {"Company": "DFW REI Club", "Website": "https://dfwreiclub.wildapricot.org/", "City": "Fort Worth, TX", "Lead_Source": "REI Club", "Contact_Name": "Robin Carriger", "Email": "", "Phone": "817-300-1132", "Notes": "Co-Founder & President, always needs wholesale deals"},

    # Wholesalepropertytx Forum
    {"Company": "WholesalePropertyTX Forum", "Website": "https://wholesalepropertytx.com/forum.html", "City": "Dallas/Fort Worth, TX", "Lead_Source": "Web Forum", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Texas wholesale real estate forum, DFW focus"},

    # AeroLeads - Top Dallas Investors
    {"Company": "Rashad Harris (Investor)", "Website": "https://aeroleads.com/list/top-real-estate-investor-in-dallas", "City": "Dallas, TX", "Lead_Source": "AeroLeads", "Contact_Name": "Rashad Harris", "Email": "", "Phone": "", "Notes": "Top Dallas real estate investor"},
    {"Company": "J.D. Robertson (Investor)", "Website": "https://aeroleads.com/list/top-real-estate-investor-in-dallas", "City": "Dallas, TX", "Lead_Source": "AeroLeads", "Contact_Name": "J.D. Robertson", "Email": "", "Phone": "", "Notes": "Top Dallas real estate investor"},
    {"Company": "Carson Goodwin (Investor)", "Website": "https://aeroleads.com/list/top-real-estate-investor-in-dallas", "City": "Dallas, TX", "Lead_Source": "AeroLeads", "Contact_Name": "Carson Goodwin", "Email": "", "Phone": "", "Notes": "Top Dallas real estate investor"},
]

# Convert to lead format
all_new_leads = []
for w in NEW_WHOLESALERS:
    lead = {
        'Lead_Type': 'Wholesaler/Buyer',
        'Company': w['Company'],
        'Contact_Name': w['Contact_Name'],
        'Email': w['Email'],
        'Phone': w['Phone'],
        'Website': w['Website'],
        'City': w['City'],
        'State': 'TX',
        'Property_Address': '',
        'Distress_Signal': '',
        'Signal_Date': '',
        'Owner_Name': '',
        'Lead_Source': w['Lead_Source'],
        'Source_File': 'web_research_expansion',
        'Status': 'New',
        'Confidence': '',
        'QA_Status': 'Pending',
        'Verification_Status': 'Pending',
        'Notes': w['Notes']
    }
    all_new_leads.append(lead)

# Load existing consolidated file
existing_file = os.path.join(ARTIFACTS, "ALL_LEADS_20260707_0007.csv")
existing_leads = []
if os.path.exists(existing_file):
    with open(existing_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_leads = list(reader)
    print(f"[+] Existing leads loaded: {len(existing_leads)}")

# Merge: add new wholesalers, avoid duplicates by Company name
existing_companies = {l.get('Company', '').lower().strip() for l in existing_leads}
added = 0
for lead in all_new_leads:
    if lead['Company'].lower().strip() not in existing_companies:
        existing_leads.append(lead)
        existing_companies.add(lead['Company'].lower().strip())
        added += 1

print(f"[+] New wholesalers added: {added}")

# Write merged file
output_file = os.path.join(ARTIFACTS, f"ALL_LEADS_EXPANDED_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Email', 'Phone', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Source_File', 'Status', 'Confidence', 'QA_Status', 'Verification_Status', 'Notes']

with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(existing_leads)

wholesaler_count = sum(1 for l in existing_leads if l['Lead_Type'] == 'Wholesaler/Buyer')
distress_count = sum(1 for l in existing_leads if l['Lead_Type'] == 'Distressed Seller')

print(f"\n{'='*50}")
print(f"EXPANDED LEADS REPORT")
print(f"{'='*50}")
print(f"Total Leads: {len(existing_leads)}")
print(f"  - Wholesalers/Buyers: {wholesaler_count}")
print(f"  - Distressed Sellers: {distress_count}")
print(f"  - Sources: Web Research, Facebook Groups, BatchLeads, RealEstateBees, HouseCashin, KeyCrew, BiggerPockets")
print(f"\nOutput: {output_file}")
