import json
import http.client
import os
import urllib.parse

rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()

def search_address(address):
    print(f"Searching Local Business Data for: {address}...")
    
    conn = http.client.HTTPSConnection("local-business-data.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': rapidapi_key,
        'x-rapidapi-host': "local-business-data.p.rapidapi.com"
    }
    query = urllib.parse.quote_plus(address)
    try:
        conn.request("GET", f"/search?query={query}&limit=5", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        
        results = data.get('data', [])
        print(f"Found {len(results)} results.")
        for r in results:
            print(f"Name: {r.get('name')}, Phone: {r.get('phone_number')}, Type: {r.get('type')}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_address("12602 TRENTON DR, DALLAS, TX, 75243")
    search_address("12124 SCHROEDER RD, DALLAS, TX, 75243")
