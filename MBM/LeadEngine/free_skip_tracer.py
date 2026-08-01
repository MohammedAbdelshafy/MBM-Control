"""
MBM Free Skip Tracer — Multi-Source Contact Enrichment
========================================================
Uses ONLY free, no-API-key sources to find phone numbers and emails.

Sources (all free, no registration required):
  1. TruePeopleSearch.com — people search by name/address
  2. ThatsThem.com — name/address/phone/email lookup
  3. ZabaSearch.com — people search by name
  4. OpenPeopleSearch.com — people search by name/address
  5. FastPeopleSearch.com — address/name search (improved scraping)
  6. DuckDuckGo HTML search — email/phone extraction from web results
  7. USPhonebook.com — reverse phone lookup

Usage:
  tracer = FreeSkipTracer()
  result = tracer.find_contact(name="John Smith", address="123 Main St, Dallas, TX")
  # result = {"phone": "...", "email": "...", "source": "...", "confidence": "high|medium|low"}

  # Batch enrich a JSON leads file:
  tracer.enrich_leads_file("global_leads.json", "enriched_leads.json")

Run: python free_skip_tracer.py --help
"""

import re
import os
import json
import time
import random
import urllib.parse
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Email domains to exclude (generic / throwaway)
EXCLUDE_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "w3.org", "rightmove.co.uk", "zoopla.co.uk",
    "google.com", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "test.com", "mailinator.com", "yopmail.com", "tempmail.com",
}


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[FREE SKIP TRACER] {timestamp} - {msg}"
    print(line)
    log_file = LOG_DIR / 'free_skip_tracer.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def extract_emails(text):
    """Extract valid emails from text, excluding generic/throwaway domains."""
    if not text:
        return []
    raw = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    valid = []
    for e in raw:
        e = e.lower().strip('.')
        domain = e.split('@')[-1]
        if domain not in EXCLUDE_EMAIL_DOMAINS and not e.startswith('noreply'):
            valid.append(e)
    return list(dict.fromkeys(valid))


def extract_phones(text):
    """Extract US phone numbers from text."""
    if not text:
        return []
    patterns = [
        r'[\+]?(?:\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}',
    ]
    phones = []
    for pat in patterns:
        for match in re.finditer(pat, text):
            raw = match.group()
            digits = re.sub(r'\D', '', raw)
            if len(digits) == 10 or (len(digits) == 11 and digits.startswith('1')):
                phones.append(raw.strip())
    return list(dict.fromkeys(phones))


def clean_name(name):
    """Normalize a name for search queries."""
    if not name:
        return ""
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'(REALTY|REALT|LLC|INC|CORP|LTD|CO\.|AGENCY|PROPERTIES|PROPERTY|SOLUTIONS|GROUP|HOMES|INVESTMENTS)',
                  '', name, flags=re.IGNORECASE).strip()
    return name


class FreeSkipTracer:
    """Multi-source free skip tracer — no API keys required."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.stats = {"total": 0, "phone_found": 0, "email_found": 0, "sources_used": {}}

    # ─── SOURCE 1: TruePeopleSearch ───

    def _search_truepeoplesearch(self, name, address=None):
        """Scrape TruePeopleSearch.com for phone + email."""
        results = []
        try:
            name_clean = clean_name(name)
            query = urllib.parse.quote_plus(name_clean)
            url = f"https://www.truepeoplesearch.com/results?name={query}"
            if address:
                addr_parts = [p.strip() for p in address.split(',')]
                if addr_parts:
                    city_state = addr_parts[-2] if len(addr_parts) >= 2 else addr_parts[0]
                    url += f"&citystatezip={urllib.parse.quote_plus(city_state)}"

            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Extract phones from result cards
                for card in soup.select('.card-phone, .phone-number, [data-phone]'):
                    phone = card.get_text(strip=True)
                    if phone:
                        extracted = extract_phones(phone)
                        results.extend([(p, "truepeoplesearch") for p in extracted])

                # Extract emails
                for card in soup.select('.card-email, .email-address, [data-email]'):
                    email = card.get_text(strip=True)
                    if email and '@' in email:
                        extracted = extract_emails(email)
                        results.extend([(e, "truepeoplesearch") for e in extracted])

                # Also scan full text for phones/emails
                full_text = soup.get_text()
                for p in extract_phones(full_text):
                    results.append((p, "truepeoplesearch"))
                for e in extract_emails(full_text):
                    results.append((e, "truepeoplesearch"))

                log(f"TruePeopleSearch: found {len(results)} items for '{name_clean}'")
        except Exception as ex:
            log(f"TruePeopleSearch error: {ex}")
        return results

    # ─── SOURCE 2: ThatsThem ───

    def _search_thatsthem(self, name, address=None):
        """Scrape ThatsThem.com for phone + email by name."""
        results = []
        try:
            name_clean = clean_name(name)
            query = urllib.parse.quote_plus(name_clean)
            url = f"https://thatsthem.com/name/{query}"

            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Extract phones
                for phone_el in soup.select('.phone, .phone-number, a[href^="tel:"]'):
                    phone = phone_el.get_text(strip=True) or phone_el.get('href', '').replace('tel:', '')
                    extracted = extract_phones(phone)
                    results.extend([(p, "thatsthem") for p in extracted])

                # Extract emails
                for email_el in soup.select('.email, .email-address, a[href^="mailto:"]'):
                    email = email_el.get_text(strip=True) or email_el.get('href', '').replace('mailto:', '').split('?')[0]
                    extracted = extract_emails(email)
                    results.extend([(e, "thatsthem") for e in extracted])

                # Scan full text
                full_text = soup.get_text()
                for p in extract_phones(full_text):
                    results.append((p, "thatsthem"))
                for e in extract_emails(full_text):
                    results.append((e, "thatsthem"))

                log(f"ThatsThem: found {len(results)} items for '{name_clean}'")
        except Exception as ex:
            log(f"ThatsThem error: {ex}")
        return results

    # ─── SOURCE 3: ZabaSearch ───

    def _search_zabasearch(self, name, address=None):
        """Scrape ZabaSearch.com for phone numbers."""
        results = []
        try:
            name_clean = clean_name(name)
            query = urllib.parse.quote_plus(name_clean)
            url = f"https://www.zabasearch.com/people/{query}"

            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                for phone_el in soup.select('.phone, .phone-number, [class*="phone"]'):
                    phone = phone_el.get_text(strip=True)
                    extracted = extract_phones(phone)
                    results.extend([(p, "zabasearch") for p in extracted])

                full_text = soup.get_text()
                for p in extract_phones(full_text):
                    results.append((p, "zabasearch"))

                log(f"ZabaSearch: found {len(results)} items for '{name_clean}'")
        except Exception as ex:
            log(f"ZabaSearch error: {ex}")
        return results

    # ─── SOURCE 4: OpenPeopleSearch ───

    def _search_openpeoplesearch(self, name, address=None):
        """Scrape OpenPeopleSearch.org for phone + email."""
        results = []
        try:
            name_clean = clean_name(name)
            query = urllib.parse.quote_plus(name_clean)
            url = f"https://openpeoplesearch.org/search?name={query}"

            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                for phone_el in soup.select('.phone, .result-phone, a[href^="tel:"]'):
                    phone = phone_el.get_text(strip=True) or phone_el.get('href', '').replace('tel:', '')
                    extracted = extract_phones(phone)
                    results.extend([(p, "openpeoplesearch") for p in extracted])

                for email_el in soup.select('.email, .result-email, a[href^="mailto:"]'):
                    email = email_el.get_text(strip=True) or email_el.get('href', '').replace('mailto:', '').split('?')[0]
                    extracted = extract_emails(email)
                    results.extend([(e, "openpeoplesearch") for e in extracted])

                full_text = soup.get_text()
                for p in extract_phones(full_text):
                    results.append((p, "openpeoplesearch"))
                for e in extract_emails(full_text):
                    results.append((e, "openpeoplesearch"))

                log(f"OpenPeopleSearch: found {len(results)} items for '{name_clean}'")
        except Exception as ex:
            log(f"OpenPeopleSearch error: {ex}")
        return results

    # ─── SOURCE 5: FastPeopleSearch (improved) ───

    def _search_fastpeoplesearch(self, name=None, address=None):
        """Scrape FastPeopleSearch.com by address or name."""
        results = []
        try:
            if address:
                # Format address for URL: street-city-state-zip
                parts = [p.strip() for p in address.split(',')]
                street = parts[0].replace(' ', '-')
                city_state = '-'.join(p.strip().replace(' ', '-') for p in parts[1:3]) if len(parts) >= 3 else ''
                url = f"https://www.fastpeoplesearch.com/address/{street}_{city_state}"

                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200 and 'Cloudflare' not in resp.text:
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Extract names and phones from result cards
                    for card in soup.select('.card, .result-card, [class*="person"]'):
                        name_el = card.select_one('h2, .name, .fullname')
                        phone_el = card.select_one('a[href^="tel:"], .phone')

                        if phone_el:
                            phone = phone_el.get_text(strip=True)
                            extracted = extract_phones(phone)
                            results.extend([(p, "fastpeoplesearch") for p in extracted])

                    full_text = soup.get_text()
                    for p in extract_phones(full_text):
                        results.append((p, "fastpeoplesearch"))
                    for e in extract_emails(full_text):
                        results.append((e, "fastpeoplesearch"))

                    log(f"FastPeopleSearch (address): found {len(results)} items")

            if name and not results:
                name_clean = clean_name(name)
                query = urllib.parse.quote_plus(name_clean)
                url = f"https://www.fastpeoplesearch.com/name/{query}"

                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200 and 'Cloudflare' not in resp.text:
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    for phone_el in soup.select('a[href^="tel:"], .phone'):
                        phone = phone_el.get_text(strip=True)
                        extracted = extract_phones(phone)
                        results.extend([(p, "fastpeoplesearch") for p in extracted])

                    full_text = soup.get_text()
                    for p in extract_phones(full_text):
                        results.append((p, "fastpeoplesearch"))
                    for e in extract_emails(full_text):
                        results.append((e, "fastpeoplesearch"))

                    log(f"FastPeopleSearch (name): found {len(results)} items")

        except Exception as ex:
            log(f"FastPeopleSearch error: {ex}")
        return results

    # ─── SOURCE 6: DuckDuckGo Email/Phone Search ───

    def _search_duckduckgo(self, name, city=None):
        """Search DuckDuckGo HTML for emails and phone numbers."""
        results = []
        try:
            name_clean = clean_name(name)
            queries = [
                f'"{name_clean}" email contact',
                f'"{name_clean}" phone number',
            ]
            if city:
                queries.insert(0, f'"{name_clean}" {city} real estate email phone')

            for query in queries:
                url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
                time.sleep(random.uniform(0.5, 1.5))

                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    text_content = soup.get_text()

                    for e in extract_emails(text_content):
                        results.append((e, "duckduckgo"))
                    for p in extract_phones(text_content):
                        results.append((p, "duckduckgo"))

                    # Also scrape result snippets
                    for snippet in soup.select('.result__snippet'):
                        snippet_text = snippet.get_text()
                        for e in extract_emails(snippet_text):
                            results.append((e, "duckduckgo"))
                        for p in extract_phones(snippet_text):
                            results.append((p, "duckduckgo"))

                    # Scrape top result links for emails
                    links = soup.select('a.result__url', limit=3)
                    for link in links:
                        href = link.get('href', '')
                        if href.startswith('//'):
                            href = 'https:' + href
                        if any(x in href.lower() for x in ['rightmove', 'zoopla', 'onthemarket', 'duckduckgo', 'google']):
                            continue
                        try:
                            time.sleep(random.uniform(0.3, 0.8))
                            page_resp = self.session.get(href, timeout=5)
                            if page_resp.status_code == 200:
                                page_text = page_resp.text
                                for e in extract_emails(page_text):
                                    results.append((e, "duckduckgo_scrape"))
                                for p in extract_phones(page_text):
                                    results.append((p, "duckduckgo_scrape"))
                        except Exception:
                            pass

                if results:
                    break

            log(f"DuckDuckGo: found {len(results)} items for '{name_clean}'")
        except Exception as ex:
            log(f"DuckDuckGo error: {ex}")
        return results

    # ─── SOURCE 7: USPhonebook ───

    def _search_usphonebook(self, name=None, phone=None):
        """Search USPhonebook.com for contact info."""
        results = []
        try:
            if phone:
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    url = f"https://www.usphonebook.com/{digits[-10:]}"
                    resp = self.session.get(url, timeout=10)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        full_text = soup.get_text()
                        for e in extract_emails(full_text):
                            results.append((e, "usphonebook"))
                        for p in extract_phones(full_text):
                            results.append((p, "usphonebook"))

            if name and not results:
                name_clean = clean_name(name)
                query = urllib.parse.quote_plus(name_clean)
                url = f"https://www.usphonebook.com/search/?type=person&query={query}"
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    full_text = soup.get_text()
                    for p in extract_phones(full_text):
                        results.append((p, "usphonebook"))
                    for e in extract_emails(full_text):
                        results.append((e, "usphonebook"))

            log(f"USPhonebook: found {len(results)} items")
        except Exception as ex:
            log(f"USPhonebook error: {ex}")
        return results

    # ─── PUBLIC API ───

    def find_contact(self, name=None, address=None, city=None):
        """
        Find phone and/or email for a person using all free sources.
        Returns: {"phone": str|None, "email": str|None, "source": str, "confidence": str}
        """
        self.stats["total"] += 1
        all_phones = []
        all_emails = []

        # Run all sources
        sources = [
            ("truepeoplesearch", lambda: self._search_truepeoplesearch(name, address)),
            ("thatsthem", lambda: self._search_thatsthem(name, address)),
            ("zabasearch", lambda: self._search_zabasearch(name, address)),
            ("openpeoplesearch", lambda: self._search_openpeoplesearch(name, address)),
            ("fastpeoplesearch", lambda: self._search_fastpeoplesearch(name, address)),
            ("duckduckgo", lambda: self._search_duckduckgo(name, city)),
        ]

        for source_name, search_fn in sources:
            try:
                items = search_fn()
                for value, src in items:
                    digits = re.sub(r'\D', '', value)
                    if len(digits) >= 10 and '@' not in value:
                        all_phones.append((value, src))
                    elif '@' in value:
                        all_emails.append((value, src))
                    self.stats["sources_used"][src] = self.stats["sources_used"].get(src, 0) + 1
            except Exception as ex:
                log(f"Source {source_name} failed: {ex}")
            time.sleep(random.uniform(0.3, 1.0))

        # Pick best phone (prefer sources with higher trust)
        phone = None
        phone_source = None
        if all_phones:
            # Deduplicate by digits
            seen_digits = set()
            unique_phones = []
            for p, src in all_phones:
                d = re.sub(r'\D', '', p)
                if d not in seen_digits:
                    seen_digits.add(d)
                    unique_phones.append((p, src))
            if unique_phones:
                phone = unique_phones[0][0]
                phone_source = unique_phones[0][1]
                self.stats["phone_found"] += 1

        # Pick best email
        email = None
        email_source = None
        if all_emails:
            seen_emails = set()
            unique_emails = []
            for e, src in all_emails:
                if e.lower() not in seen_emails:
                    seen_emails.add(e.lower())
                    unique_emails.append((e, src))
            if unique_emails:
                email = unique_emails[0][0]
                email_source = unique_emails[0][1]
                self.stats["email_found"] += 1

        # Determine confidence
        confidence = "low"
        if phone and email:
            confidence = "high"
        elif phone or email:
            confidence = "medium"

        source = phone_source or email_source or "none"

        result = {
            "phone": phone,
            "email": email,
            "source": source,
            "confidence": confidence,
            "all_phones": [p for p, _ in all_phones[:5]],
            "all_emails": [e for e, _ in all_emails[:5]],
        }

        if phone or email:
            log(f"FOUND CONTACT for '{name}': phone={phone} ({phone_source}), email={email} ({email_source})")
        else:
            log(f"No contact found for '{name}'")

        return result

    def find_phone(self, name=None, address=None, city=None):
        """Shortcut: find only phone number."""
        result = self.find_contact(name=name, address=address, city=city)
        return result.get("phone")

    def find_email(self, name=None, city=None):
        """Shortcut: find only email."""
        result = self.find_contact(name=name, city=city)
        return result.get("email")

    def enrich_leads_file(self, input_path, output_path=None):
        """
        Enrich a JSON leads file with phone + email from free sources.
        Expects leads to have 'agent'/'name' and optionally 'address'/'city' fields.
        """
        if not os.path.exists(input_path):
            log(f"File not found: {input_path}")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            leads = json.load(f)

        log(f"Enriching {len(leads)} leads from {input_path}...")
        enriched = 0

        for i, lead in enumerate(leads):
            name = lead.get('agent') or lead.get('name') or lead.get('Owner_Name') or lead.get('contact_name', '')
            address = lead.get('address') or lead.get('Property_Address', '')
            city = lead.get('city', '')
            if not city and ',' in address:
                city = address.split(',')[-1].strip()

            # Skip if already has both phone and email
            existing_phone = lead.get('phone') or lead.get('Phone') or lead.get('agent_phone')
            existing_email = lead.get('email') or lead.get('Email') or lead.get('agent_email')
            if existing_phone and existing_email:
                continue

            result = self.find_contact(name=name, address=address, city=city)

            if result["phone"] and not existing_phone:
                lead['phone'] = result["phone"]
                lead['agent_phone'] = result["phone"]
                enriched += 1
            if result["email"] and not existing_email:
                lead['email'] = result["email"]
                lead['agent_email'] = result["email"]
                enriched += 1

            lead['skip_trace_source'] = result["source"]
            lead['skip_trace_confidence'] = result["confidence"]

            # Rate limit
            time.sleep(random.uniform(0.5, 1.5))

            if (i + 1) % 10 == 0:
                log(f"Progress: {i + 1}/{len(leads)} leads processed, {enriched} enriched")

        # Save
        if not output_path:
            output_path = input_path.replace('.json', '_enriched.json')

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, default=str)

        log(f"Enrichment complete: {enriched}/{len(leads)} contacts added")
        log(f"Stats: {json.dumps(self.stats)}")
        log(f"Saved to: {output_path}")
        return output_path

    def get_stats(self):
        return self.stats


# ─── CLI ───

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MBM Free Skip Tracer — Multi-source contact enrichment")
    parser.add_argument("--name", type=str, help="Person name to search")
    parser.add_argument("--address", type=str, help="Property address to search")
    parser.add_argument("--city", type=str, help="City for search context")
    parser.add_argument("--enrich", type=str, help="Path to JSON leads file to enrich")
    parser.add_argument("--output", type=str, help="Output path (default: input_enriched.json)")
    args = parser.parse_args()

    tracer = FreeSkipTracer()

    if args.enrich:
        tracer.enrich_leads_file(args.enrich, args.output)
    elif args.name or args.address:
        result = tracer.find_contact(name=args.name, address=args.address, city=args.city)
        print(json.dumps(result, indent=2))
    else:
        # Self-test
        print("=== FREE SKIP TRACER SELF-TEST ===")
        test_result = tracer.find_contact(name="John Smith", address="123 Main St, Dallas, TX", city="Dallas")
        print(json.dumps(test_result, indent=2))
        print(f"\nStats: {json.dumps(tracer.get_stats(), indent=2)}")
