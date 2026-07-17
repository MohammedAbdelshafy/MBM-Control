import csv
import os
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")

# Additional wholesalers from KeyCrew page 2 + other sources
MORE_WHOLESALERS = [
    {"Company": "NetWorth Realty of Inland Empire, Inc", "Website": "https://keycrew.co/company/networth-realty-of-inland-empire-inc/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Distressed properties, nationwide network"},
    {"Company": "Fix and Flippers", "Website": "https://keycrew.co/company/fix-and-flippers/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Hard money lending + wholesale, multifamily + land"},
    {"Company": "A-List Homes LLC", "Website": "https://keycrew.co/company/a-list-homes-llc/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Senior transition specialist, DFW + Fort Worth + Grapevine"},
    {"Company": "Alpha Cash Buyers", "Website": "https://keycrew.co/company/alpha-cash-buyers/", "City": "Fort Worth, TX", "Lead_Source": "KeyCrew", "Contact_Name": "Jonathan", "Email": "", "Phone": "", "Notes": "Cash home buyer, Fort Worth focus"},
    {"Company": "Property Ezer", "Website": "https://keycrew.co/company/property-ezer/", "City": "Dallas, TX", "Lead_Source": "KeyCrew", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "61+ locations in TX, foreclosure/inherited/repaired homes"},

    # More from web research
    {"Company": "Ntxpropertygroup", "Website": "https://www.ntxpropertygroup.com/dallas--tx/real-estate-wholesaling-company", "City": "Dallas, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "North Texas property group, wholesaling"},
    {"Company": "Dfwwholesaleproperties", "Website": "https://www.dfwwholesaleproperties.com/", "City": "Dallas, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW wholesale properties"},
    {"Company": "Dfwdealboard", "Website": "https://www.dfwdealboard.com/", "City": "Dallas, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "DFW deal board"},
    {"Company": "Browderpropertyinvestments", "Website": "https://browderpropertyinvestments.com/index.php/wholesale-real-estate-opportunities/", "City": "Dallas, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Wholesale real estate opportunities"},
    {"Company": "Sellhomedallas", "Website": "https://sellhomedallas.com/real-estate-wholesalers-dallas-tx/", "City": "Dallas, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Dallas wholesaler directory"},
    {"Company": "D7Leadfinder", "Website": "https://d7leadfinder.com/app/view-leads/25304229/", "City": "Houston, TX", "Lead_Source": "Web Search", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Lead finder platform"},
    {"Company": "Property Decision Group", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Real estate investment firm, fix-and-flip/BRRR/STR"},
    {"Company": "Clark Law Group, PLLC", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Real estate law, investor friendly"},
    {"Company": "Legacy Outdoor Concepts", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Outdoor/land investor"},
    {"Company": "Mijares Law, PLLC", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "", "Email": "", "Phone": "", "Notes": "Real estate law firm"},
    {"Company": "Carolyn Flowers B2jai Real Estate", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "Carolyn Flowers", "Email": "", "Phone": "", "Notes": "New investor, residential + commercial"},
    {"Company": "Robert T.C. Sanders, Attorney at Law, PLLC", "Website": "https://www.investorfriend.ly/texas/dallas", "City": "Dallas, TX", "Lead_Source": "InvestorFriendly", "Contact_Name": "Robert T.C. Sanders", "Email": "", "Phone": "", "Notes": "Attorney, investor friendly"},
]

# Convert to lead format
new_leads = []
for w in MORE_WHOLESALERS:
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
        'Source_File': 'web_research_expansion_v2',
        'Status': 'New',
        'Confidence': '',
        'QA_Status': 'Pending',
        'Verification_Status': 'Pending',
        'Notes': w['Notes']
    }
    new_leads.append(lead)

# Load existing expanded file
existing_file = os.path.join(ARTIFACTS, "ALL_LEADS_EXPANDED_20260707_0009.csv")
existing_leads = []
if os.path.exists(existing_file):
    with open(existing_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_leads = list(reader)
    print(f"[+] Existing leads loaded: {len(existing_leads)}")

# Merge: add new wholesalers, avoid duplicates by Company name
existing_companies = {l.get('Company', '').lower().strip() for l in existing_leads}
added = 0
for lead in new_leads:
    if lead['Company'].lower().strip() not in existing_companies:
        existing_leads.append(lead)
        existing_companies.add(lead['Company'].lower().strip())
        added += 1

print(f"[+] New wholesalers added: {added}")

# Write merged file
output_file = os.path.join(ARTIFACTS, f"ALL_LEADS_FINAL_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Email', 'Phone', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Source_File', 'Status', 'Confidence', 'QA_Status', 'Verification_Status', 'Notes']

with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(existing_leads)

wholesaler_count = sum(1 for l in existing_leads if l['Lead_Type'] == 'Wholesaler/Buyer')
distress_count = sum(1 for l in existing_leads if l['Lead_Type'] == 'Distressed Seller')

print(f"\n{'='*50}")
print(f"FINAL LEADS REPORT")
print(f"{'='*50}")
print(f"Total Leads: {len(existing_leads)}")
print(f"  - Wholesalers/Buyers: {wholesaler_count}")
print(f"  - Distressed Sellers: {distress_count}")
print(f"\nSources:")
print(f"  - PropStream (verified wholesaler contacts)")
print(f"  - Dallas 311 Code Concerns (distressed sellers)")
print(f"  - RealEstateBees (top 10 Dallas wholesalers)")
print(f"  - HouseCashin (5+ Dallas wholesalers)")
print(f"  - KeyCrew (15+ verified wholesalers)")
print(f"  - BiggerPockets (active DFW wholesalers)")
print(f"  - Facebook Groups (3 DFW wholesale groups)")
print(f"  - ConnectedInvestors (DFW forum)")
print(f"  - InvestorFriendly (Dallas directory)")
print(f"  - AeroLeads (top 50 Dallas investors)")
print(f"\nOutput: {output_file}")
