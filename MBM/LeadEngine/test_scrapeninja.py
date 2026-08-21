import json
import http.client
import os
import re
from bs4 import BeautifulSoup

rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()

def ninja_reverse_phone(phone):
    digits = re.sub(r'\D', '', phone)
    url = f"https://www.truepeoplesearch.com/results?phoneno={digits}"
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
        print(f"Status: {data.get('info', {}).get('statusCode')}")
        print(f"Body snippet: {body_html[:500]}")
        soup = BeautifulSoup(body_html, 'html.parser')
        
        # In TruePeopleSearch, names are often in h1, h4, .oh1, .h4
        for el in soup.select('.oh1, .h4, .card-title, .name-link'):
            n = el.get_text(strip=True)
            if n and len(n) > 2 and "Phone" not in n and "Search" not in n:
                print(f"Found candidate: {n}")
                name = n.split(',')[0].title()
                return name
                
    except Exception as e:
        print(f"Error: {e}")
    return None

if __name__ == "__main__":
    # Test with an Atlanta area code format
    print(ninja_reverse_phone("4048493721"))
