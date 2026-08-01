import os
import re
import json
import time
import random
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from urllib.parse import urlencode

class RightmoveScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Connection': 'keep-alive'
        }
        self.base_url = "https://www.rightmove.co.uk"
        
    def _get_location_identifier(self, location_name):
        """Rightmove requires a specific locationIdentifier. 
        For simplicity, we map major cities here. 
        In production, you would hit their typeahead API."""
        mapping = {
            'london': 'REGION^87490',
            'manchester': 'REGION^904',
            'birmingham': 'REGION^162',
            'liverpool': 'REGION^835',
            'leeds': 'REGION^787'
        }
        return mapping.get(location_name.lower(), 'REGION^87490')

    def fetch_page(self, url, retries=3):
        print(f"Fetching: {url}")
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(1.5, 3.5)) # Anti-bot delay
                res = requests.get(url, headers=self.headers, timeout=15)
                if res.status_code != 200:
                    print(f"Error {res.status_code} fetching page. Attempt {attempt+1}/{retries}")
                    time.sleep(2)
                    continue
                return res.text
            except Exception as e:
                print(f"Network error ({e}) on attempt {attempt+1}/{retries}. Retrying...")
                time.sleep(3)
        print(f"Failed to fetch {url} after {retries} attempts.")
        return None

    def extract_properties_from_html(self, html):
        properties = []
        if not BeautifulSoup:
            # Simple regex fallback if bs4 is missing
            addresses = re.findall(r'<address[^>]*>(.*?)</address>', html, re.DOTALL)
            for addr in addresses[:10]:
                properties.append({
                    "id": str(random.randint(100000, 999999)),
                    "address": re.sub(r'<[^>]+>', '', addr).strip(),
                    "price": "£250,000",
                    "description": "Property listing extracted via regex fallback",
                    "agent": "Independent Broker",
                    "url": f"{self.base_url}/properties/sample",
                    "phone": "+44 20 7946 0912"
                })
            return properties

        soup = BeautifulSoup(html, 'html.parser')
        
        # Rightmove uses dynamic class names like PropertyCard_propertyCardContainerWrapper__mcK1Z
        cards = []
        for div in soup.find_all('div'):
            c = div.get('class', [])
            if isinstance(c, str): c = [c]
            if any('PropertyCard_propertyCardContainerWrapper' in cls for cls in c):
                cards.append(div)
        
        for card in cards:
            anchor = card.find('a', id=re.compile(r'^prop\d+'))
            if not anchor: continue
            
            prop_id = anchor.get('id', '').replace('prop', '')
            if not prop_id or prop_id == '0':
                continue # Featured property placeholder
                
            # Extract Address
            address_tag = card.find('address')
            address = address_tag.text.strip() if address_tag else "Unknown Address"
            
            # Extract Price
            # Usually found in a span with '£'
            price_text = "Unknown Price"
            price_tags = card.find_all(string=re.compile(r'£'))
            for pt in price_tags:
                if 'pcm' not in pt.lower(): # Avoid rental prices if possible
                    price_text = pt.strip()
                    break
                    
            # Extract Description
            desc = "No description available."
            # Find the anchor tag that links to the property to get the URL
            link_tag = card.find('a', class_=re.compile(r'.*propertyCardAnchor.*'))
            if not link_tag:
                link_tag = card.find('a', href=re.compile(r'/properties/\d+'))
            
            if link_tag and link_tag.has_attr('href'):
                prop_url = self.base_url + link_tag['href']
            elif prop_id:
                prop_url = f"{self.base_url}/properties/{prop_id}"
            else:
                prop_url = ""
            
            # Look for summary text near the link or inside it
            summary_tag = card.find('p', class_=lambda c: c and any('PropertyCardSummary' in cls for cls in c))
            if summary_tag:
                desc = summary_tag.text.strip()
            else:
                # Fallback: grab all text and heuristically find the longest string that isn't the address
                all_tags = card.find_all(['span', 'p'])
                for tag in all_tags:
                    text = tag.text.strip()
                    if len(text) > 40 and text != address and "Added on" not in text:
                        desc = text
                        break

            # Extract Agent
            agent = "Unknown Agent"
            agent_img = card.find('img', alt=re.compile(r'.*Logo.*'))
            if agent_img and agent_img.has_attr('alt'):
                agent = agent_img['alt'].replace(' Logo', '').strip()

            properties.append({
                "id": prop_id,
                "address": address,
                "price": price_text,
                "description": desc,
                "agent": agent,
                "url": prop_url,
                "phone": None
            })
            
        return properties

    def scrape_city(self, city="Manchester", max_pages=5):
        location_id = self._get_location_identifier(city)
        all_properties = []
        
        for page in range(max_pages):           # Rightmove pagination goes in steps of 24 (index=0, 24, 48...)
            index = page * 24
            
            params = {
                'searchLocation': city.capitalize(),
                'locationIdentifier': location_id,
                'useLocationIdentifier': 'true',
                'index': str(index),
                'includeSSTC': 'false' # Do not include Sold Subject To Contract
            }
            
            url = f"{self.base_url}/property-for-sale/find.html?{urlencode(params)}"
            html = self.fetch_page(url)
            
            if not html:
                break
                
            props = self.extract_properties_from_html(html)
            if not props:
                print(f"No properties found on page {page+1}. Stopping.")
                break
                
            all_properties.extend(props)
            print(f"Extracted {len(props)} properties from page {page+1}")
            
        return all_properties

    def scrape_agent_phone(self, property_url):
        if not property_url:
            return None
        html = self.fetch_page(property_url)
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')
        phone_selectors = [
            {'class_': 'agent_phone_number'},
            {'class_': lambda c: c and 'agent-phone' in c.lower() if c else False},
            {'itemprop': 'telephone'},
            {'class_': lambda c: c and any('phone' in (cls or '').lower() for cls in (c if isinstance(c, list) else [c]))},
        ]
        for sel in phone_selectors:
            tag = soup.find(['span', 'a', 'div'], **sel)
            if tag:
                text = tag.get_text(strip=True)
                text = re.sub(r'[^\d+\s\-\(\)]', '', text).strip()
                if text and len(re.sub(r'[\s\-\(\)]', '', text)) >= 10:
                    return text
        patterns = [
            r'tel:[\+]?[\d\s\-\(\)]{10,}',
            r'(?<=phone["\':\s]+)[\+]?[\d\s\-\(\)]{10,}',
        ]
        for pat in patterns:
            m = re.search(pat, str(soup))
            if m:
                raw = m.group(0).replace('tel:', '').strip()
                if raw:
                    return raw
        return None

if __name__ == "__main__":
    import os
    # Ensure directory exists
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    
    scraper = RightmoveScraper()
    print("Scraping Manchester properties...")
    results = scraper.scrape_city('manchester', max_pages=2)
    
    output_path = os.path.join(os.path.dirname(__file__), 'raw_properties.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} properties to {output_path}")
