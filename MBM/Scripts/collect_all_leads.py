import csv
import os
from pathlib import Path
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")
BAGA = os.path.join(MBM_ROOT, "Clients", "BAGA")
OUTPUT = os.path.join(ARTIFACTS, f"ALL_LEADS_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")

all_leads = []

# 1. Wholesalers/Buyers (verified)
wholesalers_file = os.path.join(ARTIFACTS, "wholesalers_final_qualified.csv")
if os.path.exists(wholesalers_file):
    with open(wholesalers_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['Lead_Type'] = 'Wholesaler/Buyer'
            row['Source_File'] = 'wholesalers_final_qualified.csv'
            all_leads.append(row)
    print(f"[+] Loaded {len(all_leads)} wholesalers/buyers")

# 2. Distressed sellers - Dallas 311 batches
for batch_file in [
    os.path.join(BAGA, "Dallas_Distressed_Batch_01_2026-07-04.csv"),
    os.path.join(BAGA, "Dallas_Distressed_Batch_01_2026-07-02.csv")
]:
    if os.path.exists(batch_file):
        fname = os.path.basename(batch_file)
        count = 0
        with open(batch_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lead = {
                    'Lead_Type': 'Distressed Seller',
                    'Source_File': fname,
                    'Property_Address': row.get('Property_Address', ''),
                    'City': 'Dallas',
                    'State': 'TX',
                    'Distress_Signal': row.get('Distress_Signal', ''),
                    'Signal_Date': row.get('Signal_Date', ''),
                    'Owner_Name': row.get('Owner_Name', ''),
                    'Phone': row.get('Phone', ''),
                    'Company': '',
                    'Contact_Name': row.get('Owner_Name', ''),
                    'Email': '',
                    'Website': '',
                    'Lead_Source': 'Dallas 311 Code Concerns',
                    'Status': 'New',
                    'Confidence': '',
                    'QA_Status': '',
                    'Verification_Status': ''
                }
                all_leads.append(lead)
                count += 1
        print(f"[+] Loaded {count} distressed sellers from {fname}")

# Write consolidated file
fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Email', 'Phone', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Source_File', 'Status', 'Confidence', 'QA_Status', 'Verification_Status']

with open(OUTPUT, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_leads)

wholesaler_count = sum(1 for l in all_leads if l['Lead_Type'] == 'Wholesaler/Buyer')
distress_count = sum(1 for l in all_leads if l['Lead_Type'] == 'Distressed Seller')

print(f"\n{'='*50}")
print(f"CONSOLIDATED LEADS REPORT")
print(f"{'='*50}")
print(f"Total Leads: {len(all_leads)}")
print(f"  - Wholesalers/Buyers: {wholesaler_count}")
print(f"  - Distressed Sellers: {distress_count}")
print(f"\nOutput: {OUTPUT}")