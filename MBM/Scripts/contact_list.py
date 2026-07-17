"""
MBM Lead Pack - Verified Contact List
======================================
Top targets with verified emails and phone numbers.
"""

CONTACTS = [
    {
        "rank": 1,
        "company": "New Western",
        "location": "Irving, TX",
        "phone": "(972) 734-1612",
        "address": "5000 Riverside Drive, Bldg. 5, Suite 100W, Irving, TX 75039",
        "website": "newwestern.com",
        "notes": "Largest wholesale marketplace, 250K+ investors",
        "pitch": "buyer_leads"
    },
    {
        "rank": 2,
        "company": "PipHouse LLC",
        "location": "Irving, TX",
        "phone": "(469) 658-4582",
        "email": "PipHousellc@gmail.com",
        "address": "1425 W Pioneer Dr, Irving, TX 75061",
        "website": "pip-house.com",
        "notes": "Active on BiggerPockets, focuses on pre-foreclosure, probate",
        "pitch": "buyer_leads"
    },
    {
        "rank": 3,
        "company": "Swift Home Solutions",
        "location": "Plano/Hurst, TX",
        "phone": "(469) 273-1235",
        "email": "investments@swifthomesolutions.com",
        "address": "120 Precinct Line Rd, Hurst, TX 76053",
        "website": "swifthomesolutions.com",
        "notes": "DFW + San Antonio, LinkedIn 1.5K followers",
        "pitch": "seller_leads"
    },
    {
        "rank": 4,
        "company": "We Buy Houses Fast Dallas",
        "location": "Dallas, TX",
        "phone": "(469) 461-4209",
        "website": "sellmyhousefastindallas.com",
        "notes": "Residential, multi-family, commercial",
        "pitch": "seller_leads"
    },
    {
        "rank": 5,
        "company": "Diamond Acquisitions",
        "location": "Dallas, TX",
        "phone": "(469) 436-4884",
        "email": "diamondacquisitions@outlook.com",
        "address": "15770 Dallas Pkwy #1150, Dallas, TX 75248",
        "website": "offer.diamondacquisitions.biz",
        "notes": "Cash buyer, DFW metro",
        "pitch": "seller_leads"
    },
    {
        "rank": 6,
        "company": "DFW REI Club",
        "location": "Fort Worth, TX",
        "phone": "(817) 300-1132",
        "contact": "Robin Carriger",
        "notes": "Always in need of wholesale deals",
        "pitch": "buyer_leads"
    },
    {
        "rank": 7,
        "company": "No Worries Home Sale",
        "location": "Fort Worth, TX",
        "website": "noworrieshomesale.com",
        "notes": "Foreclosure, divorce, inherited properties",
        "pitch": "seller_leads"
    },
    {
        "rank": 8,
        "company": "Alpha Cash Buyers",
        "location": "Fort Worth, TX",
        "website": "alphacashbuyers.com",
        "notes": "Cash buyer",
        "pitch": "seller_leads"
    },
    {
        "rank": 9,
        "company": "Easy Offer DFW",
        "location": "Dallas + Fort Worth",
        "website": "easyofferdfw.com",
        "notes": "DFW coverage",
        "pitch": "seller_leads"
    },
    {
        "rank": 10,
        "company": "Dallas Cash Home Buyers",
        "location": "Dallas, TX",
        "phone": "(469) 728-8664",
        "website": "dallascashhomebuyers.com",
        "notes": "Cash buyer",
        "pitch": "seller_leads"
    }
]

def print_contacts():
    print("="*70)
    print("MBM LEAD PACKS - VERIFIED CONTACT LIST")
    print("="*70)
    
    for c in CONTACTS:
        print(f"\n#{c['rank']} - {c['company']}")
        print(f"   Location: {c['location']}")
        if c.get('phone'):
            print(f"   Phone: {c['phone']}")
        if c.get('email'):
            print(f"   Email: {c['email']}")
        if c.get('address'):
            print(f"   Address: {c['address']}")
        if c.get('website'):
            print(f"   Website: {c['website']}")
        if c.get('contact'):
            print(f"   Contact: {c['contact']}")
        print(f"   Notes: {c['notes']}")
        print(f"   Pitch: {c['pitch']}")

if __name__ == "__main__":
    print_contacts()
