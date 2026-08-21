import json
import http.client
import os
import urllib.parse
from bs4 import BeautifulSoup

rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()

def ninja_search_address(address):
    # e.g. 12602 TRENTON DR, DALLAS, TX
    parts = [p.strip() for p in address.split(',')]
    street = parts[0].replace(' ', '-')
    city_state = '-'.join(p.strip().replace(' ', '-') for p in parts[1:3]) if len(parts) >= 3 else ''
    url = f"https://www.fastpeoplesearch.com/address/{street}_{city_state}"
    
    print(f"Scraping {url} via ScrapeNinja...")
    
    conn = http.client.HTTPSConnection("scrapeninja.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': rapidapi_key,
        'x-rapidapi-host': "scrapeninja.p.rapidapi.com",
        'Content-Type': "application/json"
    }
    payload = json.dumps({"url": url})
    
    try:
        conn.request("POST", "/scrape", payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        body_html = data.get('body', '')
        
        soup = BeautifulSoup(body_html, 'html.parser')
        print("Page Title:", soup.title.get_text() if soup.title else "No Title")
        
        # Check if Cloudflare
        if "Cloudflare" in body_html or "Just a moment" in body_html:
            print("Blocked by Cloudflare!")
            return
            
        # FastPeopleSearch names
        names = set()
        for el in soup.select('h2, .name, .fullname, a[title*="Find all information"]'):
            n = el.get_text(strip=True)
            if len(n) > 2 and "Phone" not in n:
                names.add(n)
        
        phones = set()
        for el in soup.select('a[href^="tel:"], .phone, strong'):
            p = el.get_text(strip=True)
            if len(p) >= 10:
                phones.add(p)
                
        print("Found Names:", list(names))
        print("Found Phones:", list(phones))
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    ninja_search_address("12602 TRENTON DR, DALLAS, TX, 75243")
