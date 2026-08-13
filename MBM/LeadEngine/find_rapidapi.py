import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

query = 'site:rapidapi.com "skip-tracing-working-api" endpoint'
url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"

try:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for snippet in soup.select('.result__snippet'):
        print(snippet.get_text())
        
    query2 = '"skip-tracing-working-api" python requests'
    url2 = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query2)}"
    resp2 = requests.get(url2, headers=HEADERS, timeout=10)
    soup2 = BeautifulSoup(resp2.text, 'html.parser')
    for snippet in soup2.select('.result__snippet'):
        print(snippet.get_text())
        
except Exception as e:
    print(f"Error: {e}")
