import json
import os
import re
from urllib.parse import quote
from contact_enrichment import ContactEnricher

LEADS_FILE = os.path.join(os.path.dirname(__file__), 'enriched_global_leads.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'whatsapp_sms_campaign.json')

def clean_phone_for_whatsapp(phone):
    if not phone:
        return None
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return None
    if digits.startswith('44') or digits.startswith('1'):
        return digits
    if digits.startswith('0') and len(digits) == 11:
        return '44' + digits[1:]
    return digits

def generate_whatsapp_campaign():
    if not os.path.exists(LEADS_FILE):
        print("No enriched leads file found.")
        return

    with open(LEADS_FILE, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    enricher = ContactEnricher()
    campaign_data = []

    for lead in leads:
        agent = lead.get('agent', 'Property Manager')
        address = lead.get('address', 'the property')
        price = lead.get('price', 'the listing price')
        city = address.split(',')[-1].strip()

        phone = lead.get('phone')
        if not phone:
            info = enricher.search_agency_email(agent, city)
            if isinstance(info, dict):
                phone = info.get('phone')

        clean_num = clean_phone_for_whatsapp(phone)
        if not clean_num:
            continue

        sms_text = f"Hi {agent}, we saw your listing for {address} ({price}). We are cash buyers ready to submit an offer and move fast. Do you have 10 mins for a quick Google Meet call this week?"
        wa_link = f"https://wa.me/{clean_num}?text={quote(sms_text)}"

        entry = {
            "agent": agent,
            "address": address,
            "price": price,
            "raw_phone": phone,
            "clean_phone": clean_num,
            "whatsapp_link": wa_link,
            "sms_text": sms_text
        }
        campaign_data.append(entry)
        print(f"Generated WhatsApp link for {agent}: {wa_link[:60]}...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(campaign_data, f, indent=2)

    print(f"\n==================================================")
    print(f"WHATSAPP & SMS CAMPAIGN GENERATED: {len(campaign_data)} CONTACTS")
    print(f"==================================================")

if __name__ == "__main__":
    generate_whatsapp_campaign()
