import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def reverse_phone(phone):
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 10:
        return None
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
        
    url = f"https://www.truepeoplesearch.com/results?phoneno={digits}"
    print(f"GET {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # TruePeopleSearch lists the name in an h1 with class "oh1" or h4
            for el in soup.select('.oh1, .h4, .card-title, .name-link'):
                n = el.get_text(strip=True)
                if n and len(n) > 2 and "Phone" not in n and "Search" not in n:
                    print(f"Found candidate: {n}")
                    return n.split(',')[0].title()
    except Exception as e:
        print(f"Error: {e}")
    return None

if __name__ == "__main__":
    print(reverse_phone("2124567890"))
