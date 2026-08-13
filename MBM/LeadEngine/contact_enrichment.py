import re
import requests
import time
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from urllib.parse import quote_plus

import os
import json
from dotenv import load_dotenv

load_dotenv()

class ContactEnricher:
    def __init__(self):
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Lazy-load free skip tracer to avoid circular imports
        self._free_tracer = None

    @property
    def free_tracer(self):
        if self._free_tracer is None:
            try:
                from free_skip_tracer import FreeSkipTracer
                self._free_tracer = FreeSkipTracer()
            except ImportError:
                pass
        return self._free_tracer
        
    def extract_emails(self, text):
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        valid_emails = []
        for e in emails:
            e = e.lower()
            if not any(x in e for x in ['example.com', 'sentry.io', 'w3.org', 'rightmove.co.uk', 'zoopla.co.uk']):
                valid_emails.append(e)
        return list(set(valid_emails))

    def search_agency_email(self, agent_name, city):
        """
        Uses Local Business Data API (RapidAPI) or DuckDuckGo HTML search to find email addresses.
        """
        print(f"Enriching contact for: {agent_name} in {city}...")
        
        # 1. Try RapidAPI Local Business Data if key is available
        if self.rapidapi_key:
            try:
                import http.client
                conn = http.client.HTTPSConnection("local-business-data.p.rapidapi.com")
                headers = {
                    'x-rapidapi-key': self.rapidapi_key,
                    'x-rapidapi-host': "local-business-data.p.rapidapi.com"
                }
                query = f"{agent_name} in {city}"
                conn.request("GET", f"/search?query={quote_plus(query)}&limit=1", headers=headers)
                res = conn.getresponse()
                data = json.loads(res.read().decode("utf-8"))
                
                for item in data.get('data', []):
                    emails = item.get('emails', [])
                    website = item.get('website')
                    phone = item.get('phone_number')
                    
                    if emails:
                        print(f"Found 100% verified email via RapidAPI Local Business Data: {emails[0]}")
                        return {"email": emails[0], "phone": phone, "website": website}
                        
                    # If no email in direct parameters, use ScrapeNinja to scrape agency website
                    if website:
                        print(f"Scraping official agency website via ScrapeNinja: {website}")
                        try:
                            import http.client
                            ninja_conn = http.client.HTTPSConnection("scrapeninja.p.rapidapi.com")
                            ninja_headers = {
                                'x-rapidapi-key': self.rapidapi_key,
                                'x-rapidapi-host': "scrapeninja.p.rapidapi.com",
                                'Content-Type': "application/json"
                            }
                            ninja_payload = json.dumps({"url": website})
                            ninja_conn.request("POST", "/scrape", ninja_payload, ninja_headers)
                            ninja_res = ninja_conn.getresponse()
                            ninja_data = json.loads(ninja_res.read().decode("utf-8"))
                            body_html = ninja_data.get('body', '')
                            
                            site_emails = self.extract_emails(body_html)
                            if site_emails:
                                print(f"Found verified email on website via ScrapeNinja: {site_emails[0]}")
                                return {"email": site_emails[0], "phone": phone, "website": website}
                        except Exception as ne:
                            print(f"ScrapeNinja website extraction error: {ne}")
                            
                    if phone:
                        print(f"Found verified phone via RapidAPI: {phone}")
                        return {"email": None, "phone": phone, "website": website}
            except Exception as e:
                print(f"RapidAPI Local Business Data lookup failed: {e}")

        # 2. DuckDuckGo Search Fallback
        query = f'"{agent_name}" {city} real estate email contact'
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        try:
            print(f"Enriching contact for: {agent_name} in {city}...")
            time.sleep(1) # Prevent rate limiting
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                if BeautifulSoup:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    text_content = soup.get_text()
                else:
                    text_content = re.sub(r'<[^>]+>', ' ', res.text)
                
                emails = self.extract_emails(text_content)
                
                if emails:
                    print(f"Found emails via search snippet: {emails}")
                    return emails[0]
                    
                # If no emails in snippet, find the top 3 links and scrape them
                links = soup.find_all('a', class_='result__url', limit=5)
                for link in links:
                    href = link.get('href')
                    if not href or any(x in href for x in ['rightmove', 'zoopla', 'onthemarket', 'duckduckgo']):
                        continue
                        
                    if href.startswith('//'):
                        href = 'https:' + href
                    
                    try:
                        print(f"Scraping agency website: {href}")
                        time.sleep(1) # Be polite
                        page_res = requests.get(href, headers=self.headers, timeout=5)
                        if page_res.status_code == 200:
                            page_soup = BeautifulSoup(page_res.text, 'html.parser')
                            
                            # Check mailto links first
                            mailto_links = [a.get('href').replace('mailto:', '').split('?')[0].strip() for a in page_soup.find_all('a', href=True) if 'mailto:' in a.get('href')]
                            valid_mailto = [e for e in mailto_links if '@' in e]
                            if valid_mailto:
                                print(f"Found email via mailto link: {valid_mailto[0]}")
                                return valid_mailto[0]
                                
                            # Fallback to regex on text
                            page_emails = self.extract_emails(page_soup.get_text())
                            if page_emails:
                                print(f"Found emails on website text: {page_emails}")
                                return page_emails[0]
                    except Exception as e:
                        print(f"Failed to scrape {href}: {e}")
                        continue
        except Exception as e:
            print(f"Search failed for {agent_name}: {e}")
            
        # 3. Free Skip Tracer — multi-source fallback (TruePeopleSearch, ThatsThem, etc.)
        if self.free_tracer:
            try:
                result = self.free_tracer.find_contact(name=agent_name, city=city)
                if result.get("email"):
                    print(f"Found email via Free Skip Tracer ({result['source']}): {result['email']}")
                    return {"email": result["email"], "phone": result.get("phone"), "website": None, "source": result["source"]}
                if result.get("phone"):
                    print(f"Found phone via Free Skip Tracer ({result['source']}): {result['phone']}")
                    return {"email": None, "phone": result["phone"], "website": None, "source": result["source"]}
            except Exception as e:
                print(f"Free Skip Tracer error: {e}")

        # NO naive truncated guessing! Only return verified email if found.
        print(f"No 100% verified public email found for {agent_name}. Skipping to prevent bounces.")
        return None

    def search_linkedin_decision_maker(self, company_name):
        """
        Uses DuckDuckGo Search to find B2B decision makers on LinkedIn.
        """
        print(f"Searching LinkedIn via DuckDuckGo for decision makers at: {company_name}...")
        query = f'site:linkedin.com/in/ "{company_name}" ("Manager" OR "Director" OR "Owner" OR "Founder" OR "CEO")'
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        try:
            time.sleep(1) # Prevent rate limiting
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                if BeautifulSoup:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    links = soup.find_all('a', class_='result__url', limit=5)
                    snippets = soup.find_all('a', class_='result__snippet', limit=5)
                    
                    decision_makers = []
                    for link, snippet in zip(links, snippets):
                        href = link.get('href')
                        if href and 'linkedin.com/in/' in href:
                            if href.startswith('//'):
                                href = 'https:' + href
                            
                            # Extract name from URL (e.g. linkedin.com/in/john-doe-123)
                            try:
                                parts = href.split('linkedin.com/in/')[1].split('/')[0].split('?')[0]
                                name = " ".join([p.capitalize() for p in parts.split('-') if not p.isdigit() and len(p) > 1])
                            except:
                                name = "Executive"
                                
                            title_text = snippet.get_text().strip()
                            
                            decision_makers.append({
                                "name": name,
                                "title": title_text[:60] + ("..." if len(title_text) > 60 else ""),
                                "linkedin": href
                            })
                    
                    if decision_makers:
                        print(f"Found {len(decision_makers)} decision makers via DuckDuckGo LinkedIn Search.")
                        return decision_makers
                else:
                    print("BeautifulSoup not available for DuckDuckGo scraping.")
        except Exception as e:
            print(f"DuckDuckGo LinkedIn search failed: {e}")
            
        return []

if __name__ == "__main__":
    enricher = ContactEnricher()
    email = enricher.search_agency_email("Philip James Kennedy", "Didsbury")
    print(f"Result: {email}")
