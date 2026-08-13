import csv
import os
import subprocess

def get_10_buyers():
    buyers = []
    with open('MBM/Artifacts/master_buyers_list.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Contact_Name') and row.get('Phone'):
                buyers.append({
                    'Name': row['Contact_Name'],
                    'Company': row['Company'],
                    'Phone': row['Phone'],
                    'Email': row['Email'],
                    'City': row['City']
                })
                if len(buyers) == 10:
                    break
    return buyers

def get_10_sellers():
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
                if len(sellers) == 10:
                    break
    return sellers

def generate_markdown():
    buyers = get_10_buyers()
    sellers = get_10_sellers()
    
    lines = []
    lines.append("# 🚨 TOP 10 DISTRESSED SELLERS (FOR CONTRACTING) 🚨")
    lines.append("--------------------------------------------------")
    for i, s in enumerate(sellers, 1):
        lines.append(f"### {i}. {s['Name']}")
        lines.append(f"- **Phone:** {s['Phone']}")
        lines.append(f"- **Motivation:** {s['Motivation']}")
        lines.append(f"- **Property:** {s['Address']}, {s['City']}, {s['State']}")
        lines.append(f"- **Action:** Call to lock up an AS-IS cash purchase agreement today.")
        lines.append("")
        
    lines.append("# 💰 TOP 10 CASH BUYERS (FOR DISPOSITION / ASSIGNMENT) 💰")
    lines.append("--------------------------------------------------")
    for i, b in enumerate(buyers, 1):
        lines.append(f"### {i}. {b['Name']} ({b['Company']})")
        lines.append(f"- **Phone:** {b['Phone']}")
        lines.append(f"- **Email:** {b['Email']}")
        lines.append(f"- **Market:** {b['City']}")
        lines.append(f"- **Action:** Pitch assigned contracts here. They are verified cash buyers.")
        lines.append("")
        
    output_path = 'MBM/LeadEngine/logs/telegram_buyers_sellers.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return output_path

if __name__ == "__main__":
    filepath = generate_markdown()
    print(f"Generated {filepath}")
    
    # Send via telegram
    subprocess.run(["python", "MBM/Scripts/telegram_bot.py", "file", filepath, "10 Distressed Buyers & Sellers (Wholesaling)"], check=True)
    print("Sent to Telegram!")
