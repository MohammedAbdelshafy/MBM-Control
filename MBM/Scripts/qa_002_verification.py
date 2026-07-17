import os
import csv
import re
import urllib.request
import urllib.error
from urllib.parse import urlparse
import ssl

# Files
INPUT_CSV = r'C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts\wholesalers_final_qualified.csv'
BASE_DIR = r'C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts'
QA_REPORT = os.path.join(BASE_DIR, 'QA_Report.md')
VERIFICATION_CSV = os.path.join(BASE_DIR, 'Verification_Report.csv')
FINAL_LEADS_CSV = os.path.join(BASE_DIR, 'Final_Qualified_Leads.csv')

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, str(email).strip()) is not None

def is_valid_phone(phone):
    # Basic check for digits and length
    digits = re.sub(r'\D', '', str(phone))
    return len(digits) >= 10

def check_website(url):
    if not url or not str(url).startswith('http'):
        return False, "Invalid URL format", ""
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        response = urllib.request.urlopen(req, timeout=5, context=ctx)
        html = response.read().decode('utf-8', errors='ignore')
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""
        
        return True, "200 OK", title
    except urllib.error.URLError as e:
        return False, str(e.reason), ""
    except Exception as e:
        return False, str(e), ""

def process_leads():
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            leads = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"File not found: {INPUT_CSV}")
        return

    verified_leads = []
    verification_report = []
    
    stats = {
        'total': len(leads),
        'passed': 0,
        'failed': 0,
        'needs_review': 0,
        'duplicates': 0,
        'dead_websites': 0,
        'invalid_emails': 0,
        'invalid_phones': 0,
        'total_confidence': 0
    }
    
    seen_emails = set()
    seen_phones = set()
    seen_websites = set()
    
    rejection_reasons = {}
    
    def log_rejection(reason):
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

    print(f"[*] Processing {len(leads)} leads for QA-002...")

    for i, lead in enumerate(leads):
        print(f"  [{i+1}/{len(leads)}] Verifying {lead.get('Company', 'Unknown')}...")
        
        company = str(lead.get('Company', '')).strip()
        email = str(lead.get('Email', '')).strip()
        phone = str(lead.get('Phone', '')).strip()
        website = str(lead.get('Website', '')).strip()
        
        evidence = []
        confidence = 20 # Base baseline
        
        is_duplicate = False
        if email in seen_emails and email != "":
            is_duplicate = True
            evidence.append("- Duplicate Email")
        if phone in seen_phones and phone != "":
            is_duplicate = True
            evidence.append("- Duplicate Phone")
        if website in seen_websites and website != "":
            is_duplicate = True
            evidence.append("- Duplicate Website")
            
        if is_duplicate:
            stats['duplicates'] += 1
            log_rejection("Duplicate Record")
            confidence -= 30
            
        seen_emails.add(email)
        seen_phones.add(phone)
        seen_websites.add(website)
        
        # Phone check
        phone_valid = False
        if is_valid_phone(phone):
            phone_valid = True
            confidence += 15
            evidence.append("+ Valid Phone Format")
        else:
            stats['invalid_phones'] += 1
            evidence.append("- Invalid Phone Format")
            log_rejection("Invalid Phone")
            
        # Email check
        email_valid = False
        domain_match = False
        if is_valid_email(email):
            email_valid = True
            confidence += 15
            evidence.append("+ Valid Email Syntax")
            
            # Domain match
            email_domain = email.split('@')[-1].lower()
            try:
                website_domain = urlparse(website).netloc.lower()
                website_domain = website_domain.replace('www.', '')
                if email_domain == website_domain:
                    domain_match = True
                    confidence += 20
                    evidence.append("+ Email Domain Matches Website")
                elif email_domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'aol.com', 'outlook.com']:
                    evidence.append("- Generic Email Provider")
                    confidence -= 10
            except:
                pass
        else:
            stats['invalid_emails'] += 1
            evidence.append("- Invalid Email Syntax")
            log_rejection("Invalid Email")
            
        # Website check
        web_ok, web_msg, title = check_website(website)
        if web_ok:
            confidence += 20
            evidence.append(f"+ Website Reachable (Title: {title[:30]}...)")
            
            # Context check
            keywords = ['home', 'buy', 'real estate', 'property', 'investment', 'equity', 'acquire', 'sell']
            title_lower = title.lower()
            if any(k in title_lower for k in keywords):
                confidence += 10
                evidence.append("+ Industry Keywords found on Website")
            else:
                evidence.append("- Missing Industry Keywords on Website")
        else:
            stats['dead_websites'] += 1
            confidence -= 20
            evidence.append(f"- Dead Website ({web_msg})")
            log_rejection("Dead/Unreachable Website")
            
        # Cap confidence
        confidence = max(0, min(100, confidence))
        
        if confidence >= 80 and not is_duplicate:
            v_status = "Verified"
            stats['passed'] += 1
        elif confidence >= 50 and not is_duplicate:
            v_status = "Partially Verified"
            stats['needs_review'] += 1
        else:
            v_status = "Failed Verification"
            stats['failed'] += 1
            
        if v_status == "Verified" or v_status == "Partially Verified":
            stats['total_confidence'] += confidence
            
        verification_row = {
            'Company': company,
            'Website Status': 'Reachable' if web_ok else 'Dead',
            'Email Status': 'Valid' if email_valid else 'Invalid',
            'Phone Status': 'Valid' if phone_valid else 'Invalid',
            'Verification Status': v_status,
            'Confidence': confidence,
            'Evidence Summary': " | ".join(evidence)
        }
        verification_report.append(verification_row)
        
        if v_status == "Verified":
            lead['Confidence'] = confidence
            lead['Verification_Status'] = v_status
            lead['Evidence'] = " | ".join(evidence)
            verified_leads.append(lead)

    # Write Deliverables
    
    # 1. Verification_Report.csv
    with open(VERIFICATION_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Company', 'Website Status', 'Email Status', 'Phone Status', 'Verification Status', 'Confidence', 'Evidence Summary'])
        writer.writeheader()
        writer.writerows(verification_report)
        
    # 2. Final_Qualified_Leads.csv
    if verified_leads:
        with open(FINAL_LEADS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=verified_leads[0].keys())
            writer.writeheader()
            writer.writerows(verified_leads)
            
    # 3. QA_Report.md
    avg_conf = stats['total_confidence'] / (stats['passed'] + stats['needs_review']) if (stats['passed'] + stats['needs_review']) > 0 else 0
    
    # Top rejection reasons
    sorted_rejections = sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)
    
    md_content = (
        "# QA-002 Production Verification Report\n\n"
        "## Overview\n"
        f"**Total Candidates Processed:** {stats['total']}\n"
        f"**Passed Verification:** {stats['passed']}\n"
        f"**Needs Review (Partial Verification):** {stats['needs_review']}\n"
        f"**Failed Verification:** {stats['failed']}\n\n"
        f"**Average Confidence of Passed/Review:** {avg_conf:.1f}%\n\n"
        "## Granular Failures\n"
        f"- **Duplicates Detected:** {stats['duplicates']}\n"
        f"- **Dead/Unreachable Websites:** {stats['dead_websites']}\n"
        f"- **Invalid Email Syntax:** {stats['invalid_emails']}\n"
        f"- **Invalid Phone Formats:** {stats['invalid_phones']}\n\n"
        "## Top Rejection Reasons\n"
    )
    for reason, count in sorted_rejections[:5]:
        md_content += f"- **{reason}:** {count} occurrences\n"
        
    md_content += "\n## Summary\nAll verified leads are packaged in `Final_Qualified_Leads.csv`. The detailed evidence trace for every single candidate is available in `Verification_Report.csv`.\n"
    
    with open(QA_REPORT, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print("[+] QA-002 Mission Complete.")
    print(f"    Deliverables written to: {BASE_DIR}")

if __name__ == '__main__':
    process_leads()
