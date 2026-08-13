import csv
import os

def get_buyer_cities():
    cities = set()
    with open('MBM/Artifacts/master_buyers_list.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row.get('City', '')
            if city:
                # City format is often "Austin, TX". We can match the state or city
                cities.add(city.split(',')[0].strip().upper())
    return cities

def get_20_targeted_sellers(buyer_cities):
    sellers = []
    with open('MBM/Artifacts/distressed_sellers.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            phone = row.get('Phone_Number', '') or row.get('Phone', '')
            name = row.get('Name', '') or f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()
            city = row.get('City', '').upper()
            
            if name and phone and "SKIP_TRACE" not in phone and "N/A" not in phone and phone.strip() != "":
                # Only include if seller's city matches one of the buyer cities
                if city in buyer_cities:
                    sellers.append({
                        'Name': name,
                        'Phone': phone,
                        'Address': row.get('Address', 'N/A'),
                        'Motivation': row.get('Motivation', 'Distressed Seller'),
                        'City': row.get('City', 'N/A'),
                        'State': row.get('State', 'N/A')
                    })
                    if len(sellers) == 20:
                        break
    return sellers

def generate_markdown():
    buyer_cities = get_buyer_cities()
    sellers = get_20_targeted_sellers(buyer_cities)
    
    lines = []
    lines.append("# 🎯 20 TARGETED SELLERS (MATCHED TO CASH BUYERS) 🎯")
    lines.append("--------------------------------------------------")
    lines.append("These 20 distressed sellers are located in the EXACT markets where your Cash Buyers are currently buying. Lock these under contract and immediately flip them to your buyers list.")
    lines.append("")
    
    for i, s in enumerate(sellers, 1):
        lines.append(f"### {i}. {s['Name']}")
        lines.append(f"- **Phone:** {s['Phone']}")
        lines.append(f"- **Motivation:** {s['Motivation']}")
        lines.append(f"- **Property:** {s['Address']}, {s['City']}, {s['State']}")
        lines.append(f"- **Action:** Call to lock up AS-IS contract. Instant disposition potential.")
        lines.append("")
        
    output_path = 'MBM/LeadEngine/logs/telegram_targeted_sellers.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return output_path

if __name__ == "__main__":
    filepath = generate_markdown()
    print(f"Generated {filepath}")
