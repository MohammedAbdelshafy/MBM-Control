import csv
import json
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

ARTIFACTS = Path(__file__).resolve().parent.parent / "Artifacts"
OUTREACH_LOG = Path(__file__).resolve().parent.parent / "Outreach"
OUTREACH_LOG.mkdir(parents=True, exist_ok=True)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "abdelshafyclapps@gmail.com"
SENDER_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

RECIPIENTS = [
    {"name": "PipHouse LLC", "email": "PipHousellc@gmail.com"},
    {"name": "Swift Home Solutions", "email": "investments@swifthomesolutions.com"},
    {"name": "Diamond Acquisitions", "email": "diamondacquisitions@outlook.com"},
]

EMAIL_TEMPLATES = {
    "property_alert": {
        "subject": "Distressed Property Opportunity - {address}",
        "body": """Hi {recipient_name},

We have identified a distressed property in {city} that may match your investment criteria:

  Address: {address}
  Distress Signal: {signal}
  Priority Score: {score}/100
  Signal Date: {signal_date}

Owner contact: {owner_contact}

This property has been verified through our public records pipeline and scored for urgency.

Would you like us to prepare a full package with comps, repair estimates, and ARV analysis?

Best regards,
MBM Lead Operations Team
{timestamp}""",
    },
    "lead_pack_offer": {
        "subject": "Daily Lead Pack - {date} ({count} properties)",
        "body": """Hi {recipient_name},

Our daily lead pack for {date} is ready with {count} distressed properties across the DFW metroplex.

Breakdown:
  Critical Priority: {critical}
  High Priority: {high}
  Medium Priority: {medium}

All leads sourced from public records and verified for accuracy.

Reply to this email to receive the full CSV pack.

Best regards,
MBM Lead Operations Team""",
    },
    "buyer_match": {
        "subject": "Matched Property for {buyer_company}",
        "body": """Hi {buyer_contact},

We found a property matching your acquisition criteria:

  Address: {address}
  City: {city}
  Match Score: {match_score}%
  Distress Signal: {signal}

This property is already scored and qualified in our pipeline. We can connect you directly with the owner or provide a full due diligence package.

Would you like more details?

Best regards,
MBM Lead Operations Team
{timestamp}""",
    },
}

def find_latest_file(pattern: str) -> Optional[Path]:
    files = sorted(ARTIFACTS.glob(pattern))
    return files[-1] if files else None

def load_csv(path: Path) -> List[Dict]:
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def get_top_properties(scored_path: Path, min_score: int = 75, limit: int = 10) -> List[Dict]:
    leads = load_csv(scored_path)
    return [l for l in leads if int(l.get("Score", 0)) >= min_score][:limit]

def get_top_matches(matches_path: Path, min_score: float = 80.0, limit: int = 10) -> List[Dict]:
    matches = load_csv(matches_path)
    return [m for m in matches if float(m.get("Match_Score", 0)) >= min_score][:limit]

def send_email(to_email: str, to_name: str, subject: str, body: str, attachment_path: Optional[Path] = None) -> bool:
    if not SENDER_PASSWORD:
        log_outreach("SKIPPED", to_email, subject, "No GMAIL_APP_PASSWORD set")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if attachment_path and attachment_path.exists():
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{attachment_path.name}"')
                msg.attach(part)
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        log_outreach("SENT", to_email, subject, "OK")
        return True
    except Exception as e:
        log_outreach("FAILED", to_email, subject, str(e))
        return False

def log_outreach(status: str, recipient: str, subject: str, note: str):
    log_path = OUTREACH_LOG / f"outreach_log_{datetime.now().strftime('%Y%m')}.csv"
    is_new = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["Timestamp", "Status", "Recipient", "Subject", "Note"])
        writer.writerow([datetime.now().isoformat(), status, recipient, subject, note])
    print(f"  [{status}] {recipient} | {subject[:50]}")

def send_property_alerts(scored_path: Path, matches_path: Optional[Path] = None):
    props = get_top_properties(scored_path, min_score=75, limit=15)
    if not props:
        print("No high-priority properties found")
        return
    print(f"Sending property alerts for {len(props)} top properties")
    for prop in props:
        address = prop.get("Property_Address", "Unknown")
        city = prop.get("City", "Unknown")
        signal = prop.get("Distress_Signal", "N/A")
        score = prop.get("Score", "0")
        sig_date = prop.get("Signal_Date", "")
        owner = prop.get("Owner_Name", "N/A")
        owner_phone = prop.get("Owner_Phone", "")
        owner_contact = f"{owner} - {owner_phone}" if owner_phone else owner
        for recip in RECIPIENTS:
            subject = EMAIL_TEMPLATES["property_alert"]["subject"].format(address=address[:30])
            body = EMAIL_TEMPLATES["property_alert"]["body"].format(
                recipient_name=recip["name"],
                address=address,
                city=city,
                signal=signal,
                score=score,
                signal_date=sig_date,
                owner_contact=owner_contact,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
            send_email(recip["email"], recip["name"], subject, body)

def send_lead_pack_offer(scored_path: Path):
    leads = load_csv(scored_path)
    if not leads:
        print("No leads to report")
        return
    critical = sum(1 for l in leads if l.get("Priority") == "CRITICAL")
    high = sum(1 for l in leads if l.get("Priority") == "HIGH")
    medium = sum(1 for l in leads if l.get("Priority") == "MEDIUM")
    today = datetime.now().strftime("%Y-%m-%d")
    for recip in RECIPIENTS:
        subject = EMAIL_TEMPLATES["lead_pack_offer"]["subject"].format(date=today, count=len(leads))
        body = EMAIL_TEMPLATES["lead_pack_offer"]["body"].format(
            recipient_name=recip["name"],
            date=today,
            count=len(leads),
            critical=critical,
            high=high,
            medium=medium,
        )
        send_email(recip["email"], recip["name"], subject, body)

def send_buyer_matches(matches_path: Path):
    matches = get_top_matches(matches_path, min_score=80.0, limit=20)
    if not matches:
        print("No high-score matches found")
        return
    print(f"Sending buyer match alerts for {len(matches)} top matches")
    for m in matches:
        buyer_company = m.get("Buyer_Company", "Unknown")
        buyer_contact = m.get("Buyer_Contact", "Buyer")
        buyer_email = m.get("Buyer_Email", "")
        if not buyer_email or buyer_email in ("", "N/A"):
            continue
        subject = EMAIL_TEMPLATES["buyer_match"]["subject"].format(buyer_company=buyer_company)
        body = EMAIL_TEMPLATES["buyer_match"]["body"].format(
            buyer_contact=buyer_contact,
            buyer_company=buyer_company,
            address=m.get("Property_Address", "Unknown"),
            city=m.get("Property_City", "Unknown"),
            match_score=m.get("Match_Score", "0"),
            signal=m.get("Distress_Signal", "N/A"),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        send_email(buyer_email, buyer_contact, subject, body)

def main():
    scored = find_latest_file("scored_leads_*.csv")
    matches = find_latest_file("matched_leads_*.csv")
    print(f"Latest scored leads: {scored.name if scored else 'NONE'}")
    print(f"Latest match file: {matches.name if matches else 'NONE'}")
    if scored:
        print("\n--- Sending Lead Pack Offer ---")
        send_lead_pack_offer(scored)
        print("\n--- Sending Property Alerts ---")
        send_property_alerts(scored, matches)
    if matches:
        print("\n--- Sending Buyer Match Alerts ---")
        send_buyer_matches(matches)
    print("\nDone. See Outreach/outreach_log_*.csv for results.")

if __name__ == "__main__":
    main()
