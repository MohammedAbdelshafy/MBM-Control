import csv
import os

def get_20_sellers():
    sellers = []
    with open('MBM/Artifacts/distressed_sellers.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            phone = row.get('Phone_Number', '') or row.get('Phone', '')
            name = row.get('Name', '') or f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()
            
            if name and phone and "SKIP_TRACE" not in phone and "N/A" not in phone and phone.strip() != "":
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
    sellers = get_20_sellers()
    
    lines = []
    lines.append("# 🚨 20 DISTRESSED SELLERS (READY TO CONTRACT) 🚨")
    lines.append("--------------------------------------------------")
    for i, s in enumerate(sellers, 1):
        lines.append(f"### {i}. {s['Name']}")
        lines.append(f"- **Phone:** {s['Phone']}")
        lines.append(f"- **Motivation:** {s['Motivation']}")
        lines.append(f"- **Property:** {s['Address']}, {s['City']}, {s['State']}")
        lines.append(f"- **Action:** Cold call. Cash AS-IS offer.")
        lines.append("")
        
    output_path = 'MBM/LeadEngine/logs/telegram_20_sellers.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return output_path

if __name__ == "__main__":
    filepath = generate_markdown()
    print(f"Generated {filepath}")
