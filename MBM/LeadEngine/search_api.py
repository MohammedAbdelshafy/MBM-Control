import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

query = '"skip-tracing-working-api" rapidapi'
url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"

try:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for snippet in soup.select('.result__snippet'):
        # Just encode to ascii to avoid charmap errors
        text = snippet.get_text().encode('ascii', 'ignore').decode('ascii')
        print(text)
        
except Exception as e:
    print(f"Error: {e}")
