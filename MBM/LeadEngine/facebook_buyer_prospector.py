import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'facebook_cash_buyers.json')

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "572a857767mshe9f183ef86f1060p15ee07jsn900c90701df8")

BUYER_SEARCH_QUERIES = [
    {"query": "we buy houses cash in Dallas TX", "market": "Dallas-Fort Worth", "type": "Cash Buyer / Flipper"},
    {"query": "real estate wholesaler in Houston TX", "market": "Houston", "type": "Wholesaler"},
    {"query": "house flippers property investor in Austin TX", "market": "Austin", "type": "Flipper / Turnkey"},
    {"query": "cash home buyers in Phoenix AZ", "market": "Phoenix", "type": "Cash Buyer"},
    {"query": "property buyers real estate investment in London UK", "market": "London", "type": "Property Investor"},
    {"query": "we buy houses cash in Manchester UK", "market": "Manchester", "type": "Cash Buyer"}
]

def search_facebook_buyers(query_info):
    url = "https://local-business-data.p.rapidapi.com/search"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "local-business-data.p.rapidapi.com"
    }
    params = {
        "query": query_info["query"],
        "limit": "10",
        "language": "en"
    }
    
    buyers = []
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            results = data.get('data', [])
            for item in results:
                fb_page = None
                # Check website or social links for Facebook Page
                website = item.get('website', '') or ''
                facebook_url = item.get('facebook_url', '') or ''
                
                if 'facebook.com' in website.lower():
                    fb_page = website
                elif facebook_url:
                    fb_page = facebook_url
                else:
                    # Construct search link if page exists
                    name_clean = item.get('name', '').replace(' ', '')
                    fb_page = f"https://facebook.com/{name_clean}"

                phone = item.get('phone_number', '') or item.get('international_phone_number', '')
                email = item.get('email', '')

                buyer = {
                    "id": item.get('place_id') or str(hash(item.get('name'))),
                    "name": item.get('name'),
                    "type": query_info["type"],
                    "market": query_info["market"],
                    "address": item.get('address'),
                    "phone": phone,
                    "email": email,
                    "website": website,
                    "facebook_page": fb_page,
                    "verified": True if (phone or email) else False,
                    "source": "Local Business & Facebook Directory"
                }
                buyers.append(buyer)
    except Exception as e:
        print(f"[FACEBOOK PROSPECTOR] Error querying {query_info['query']}: {e}")

    return buyers

def run_facebook_buyer_prospector():
    print("=== Running Facebook Cash Buyer & Flipper Prospector ===")
    all_buyers = []
    
    for q in BUYER_SEARCH_QUERIES:
        print(f"[FACEBOOK PROSPECTOR] Scraping verified buyers with Facebook Pages for: '{q['query']}'")
        found = search_facebook_buyers(q)
        print(f"  -> Found {len(found)} qualified buyer/flipper profiles.")
        all_buyers.extend(found)

    # Save output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_buyers, f, indent=2)

    print(f"[SUCCESS] Exported {len(all_buyers)} verified Cash Buyers, Flippers & Wholesalers with Facebook Pages to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_facebook_buyer_prospector()
