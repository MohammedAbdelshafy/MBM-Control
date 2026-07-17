import csv
import re
import requests
from urllib.parse import urlparse
import time

INPUT_CSV = r'C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts\wholesaler_leads_50.csv'
OUTPUT_CSV = r'C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts\wholesalers_qa_pass.csv'
REPORT_MD = r'C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts\QA_Report.md'

def verify_website(url):
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code == 200
    except requests.RequestException:
        return False

def verify_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def verify_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10

def is_relevant(company):
    keywords = ['buyer', 'invest', 'wholesale', 'property', 'properties', 'equity', 'capital', 'acquisition', 'solution']
    return any(kw in company.lower() for kw in keywords)

def run_qa():
    print("[*] Starting QA-001 Verification...")
    
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leads = list(reader)
    except Exception as e:
        print(f"[-] Failed to read {INPUT_CSV}: {e}")
        return

    passed_leads = []
    failed_leads = []
    seen_websites = set()
    seen_emails = set()
    seen_phones = set()
    
    total = len(leads)
    duplicates = 0
    missing_data = 0
    
    print(f"[*] Analyzing {total} candidates...")
    
    for i, row in enumerate(leads):
        # Base checks
        company = row.get('Company', '').strip()
        website = row.get('Website', '').strip()
        email = row.get('Email', '').strip()
        phone = row.get('Phone', '').strip()
        
        reasons = []
        confidence = 0
        
        # 1. Missing Data Check
        if not company or not website or not email or not phone:
            missing_data += 1
            reasons.append("Missing core data fields")
        else:
            confidence += 10
            
        # 2. Duplication
        is_duplicate = False
        if website in seen_websites:
            is_duplicate = True
            reasons.append("Duplicate Website")
        if email in seen_emails:
            is_duplicate = True
            reasons.append("Duplicate Email")
        if phone in seen_phones:
            is_duplicate = True
            reasons.append("Duplicate Phone")
            
        if is_duplicate:
            duplicates += 1
            row['QA_Status'] = 'Failed'
            row['QA_Reason'] = ' | '.join(reasons)
            row['Confidence'] = 0
            failed_leads.append(row)
            continue
            
        seen_websites.add(website)
        seen_emails.add(email)
        seen_phones.add(phone)
        
        # 3. Relevance
        if is_relevant(company):
            confidence += 20
        else:
            reasons.append("Low relevance naming")
            
        # 4. Identity & Freshness
        if verify_email(email):
            confidence += 20
        else:
            reasons.append("Invalid Email Syntax")
            
        if verify_phone(phone):
            confidence += 10
        else:
            reasons.append("Implausible Phone Number")
            
        # Website check is heaviest (Network call, be careful with time, but it's only 50 max)
        if verify_website(website):
            confidence += 40
        else:
            reasons.append("Website Unreachable/Dead")
            
        row['Confidence'] = confidence
        
        if confidence >= 80:
            row['QA_Status'] = 'Passed'
            passed_leads.append(row)
        else:
            row['QA_Status'] = 'Failed'
            row['QA_Reason'] = ' | '.join(reasons) if reasons else "Low Confidence Score"
            failed_leads.append(row)
            
        print(f"  [{i+1}/{total}] {company} - Confidence: {confidence}")

    # Write Passed
    if passed_leads:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=passed_leads[0].keys())
            writer.writeheader()
            writer.writerows(passed_leads)
            
    # Generate Markdown Report
    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.write("# QA-001 Verification Report\n\n")
        f.write("### Executive Summary\n")
        f.write(f"- **Total Candidates Evaluated:** {total}\n")
        f.write(f"- **Passed Quality Threshold (>= 80%):** {len(passed_leads)}\n")
        f.write(f"- **Failed:** {len(failed_leads)}\n")
        f.write(f"- **Duplicates Removed:** {duplicates}\n")
        f.write(f"- **Missing Data Entries:** {missing_data}\n\n")
        
        f.write("### Verdict\n")
        if len(passed_leads) > 0:
            f.write(f"**Final Deliverable:** {len(passed_leads)} highly verified leads saved to `wholesalers_qa_pass.csv`.\n\n")
        else:
            f.write("**Final Deliverable:** 0. Entire batch rejected due to failing rigorous QA checks. (Scraper must be rebuilt to fetch real entities).\n\n")
            
        f.write("### Sample of Failed Leads (Top 5)\n")
        f.write("| Company | Website | Confidence | Reason |\n")
        f.write("|---|---|---|---|\n")
        for fail in failed_leads[:5]:
            f.write(f"| {fail['Company']} | {fail['Website']} | {fail['Confidence']} | {fail.get('QA_Reason', 'Failed')} |\n")

    print(f"\n[+] QA Complete. Passed: {len(passed_leads)}. Failed: {len(failed_leads)}")
    print(f"[+] Output saved to {OUTPUT_CSV} and {REPORT_MD}")

if __name__ == '__main__':
    run_qa()
