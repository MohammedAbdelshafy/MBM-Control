import csv
import json
import requests
import random

# We simulate scraping Outscraper/Google Maps to avoid needing a live API key for this step.
# In production, replace the MOCK_LEADS with actual requests.get() to Outscraper.
MOCK_LEADS = [
    {"name": "Apex Dental Clinic", "phone": "555-0101", "email": "info@apexdental.com", "niche": "Dentist"},
    {"name": "Bright Smiles Studio", "phone": "555-0102", "email": "contact@brightsmiles.com", "niche": "Dentist"},
    {"name": "City Roots Plumbing", "phone": "555-0103", "email": "dispatch@cityrootsplumbing.com", "niche": "Plumber"},
    {"name": "FlowState Pipes", "phone": "555-0104", "email": "hello@flowstatepipes.com", "niche": "Plumber"},
    {"name": "ClearView Optometry", "phone": "555-0105", "email": "reception@clearview.com", "niche": "Optometrist"}
]

def scrape_local_businesses(niche: str, location: str, num_leads: int = 5):
    """
    Extracts local businesses. Generates a CSV file formatted for cold email outreach.
    """
    print(f"Scraping {niche} in {location}...")
    
    # Simulate API delay
    leads = []
    for i in range(num_leads):
        # Pick a random mock lead matching the niche or just generic if not enough mock data
        lead = random.choice([l for l in MOCK_LEADS if l["niche"] == niche] or MOCK_LEADS)
        # Randomize name slightly for the test
        lead_copy = lead.copy()
        lead_copy["name"] = f"{lead['name']} #{i+1}"
        leads.append(lead_copy)
        
    return leads

def save_to_csv(leads, filename="leads_database.csv"):
    if not leads:
        print("No leads to save.")
        return

    keys = leads[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(leads)
    print(f"Saved {len(leads)} leads to {filename}")

if __name__ == "__main__":
    target_niche = "Dentist"
    target_location = "Austin, TX"
    
    print("--- LEAD ENGINE STARTED ---")
    extracted_leads = scrape_local_businesses(target_niche, target_location, num_leads=5)
    save_to_csv(extracted_leads, "MBM/Scripts/b2b_sales/leads_database.csv")
