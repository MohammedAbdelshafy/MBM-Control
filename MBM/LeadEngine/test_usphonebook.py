import requests
import re
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def check_usphonebook(phone):
    digits = re.sub(r'\D', '', phone)
    url = f"https://www.usphonebook.com/{digits[-10:]}"
    print(f"GET {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Look for h1 or names
            for h1 in soup.find_all('h1'):
                print("H1:", h1.get_text(strip=True))
            for h2 in soup.find_all('h2'):
                print("H2:", h2.get_text(strip=True))
    except Exception as e:
        print(f"Error: {e}")

check_usphonebook("4048493721") # Trying an Atlanta area code format, random digits.
