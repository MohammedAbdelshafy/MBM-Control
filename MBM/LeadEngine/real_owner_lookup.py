import urllib.request
import urllib.parse
import re
import json
from bs4 import BeautifulSoup

def search_owner(address):
    query = f'"{address}" owner tax parcel OR "dallas CAD" OR "dallascad"'
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__snippet'):
            text = a.get_text()
            results.append(text)
        snippet = " ".join(results)
        
        # Try regex for typical name patterns (e.g. Owner: John Smith or LLC)
        owner_match = re.search(r'(?:owner|name|parcel|property of)\s*[:\-]?\s*([A-Z][a-z]+\s+[A-Z][a-z]+|[A-Z0-9\s,]+LLC|[A-Z0-9\s,]+INC)', snippet, re.IGNORECASE)
        if owner_match:
            return owner_match.group(1).strip()
    except Exception as e:
        print("Search error:", e)
    return None

print("Testing owner search for '12124 SCHROEDER RD, DALLAS, TX'...")
res = search_owner("12124 SCHROEDER RD, DALLAS, TX")
print("Found owner:", res)
