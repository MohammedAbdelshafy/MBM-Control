"""
MBM Lead Pack - Agency Outreach Templates
==========================================
Email and DM templates for selling lead packs to real estate agencies.
"""

TEMPLATES = {
    "cold_email_agency": {
        "subject": "Daily DFW Distressed Seller & Wholesaler Leads - Free Sample Attached",
        "body": """Hi [NAME],

I run a lead generation service focused on the DFW real estate market. We pull fresh, daily leads from public records including:

- Dallas 311 code violations (distressed sellers)
- OpenStreetMap verified wholesalers
- RealEstateBees, HouseCashin, KeyCrew directories
- BiggerPockets active investors

**What we deliver every morning by 9 AM CT:**

1. **Seller Leads** (300-600/day): Property addresses, owner names, distress signals, confidence scores
2. **Buyer/Wholesaler Leads** (50-100/day): Company names, contacts, websites, verified sources

I'd love to send you a free sample pack so you can see the quality. No strings attached.

**Pricing:**
- Single pack (seller OR buyer): $25/day
- Full pack (both): $40/day
- Monthly subscription: $500/month (22 working days)

Are you open to a quick 5-minute call this week? I can walk you through the data and send over a sample.

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com
"""
    },

    "cold_email_investor": {
        "subject": "Fresh DFW Wholesale Deals - Daily Leads from Public Records",
        "body": """Hi [NAME],

I noticed you're active in the DFW real estate space. I run a daily lead service that pulls fresh distressed seller and wholesaler leads from public records.

**Today's sample:**
- 375 distressed sellers (Dallas 311 code violations)
- 72 verified wholesalers and cash buyers
- Sources: Dallas Open Data API, KeyCrew, HouseCashin, RealEstateBees

I'd like to offer you a free week of leads to test the quality. No payment required - just reply with your email and I'll send the pack.

**Pricing if you want to continue:**
- $25/day for sellers OR buyers
- $40/day for both
- $500/month unlimited

Want me to send this week's pack?

Best,
Mohammed Abdelshafy
+201040404118
"""
    },

    "follow_up_email": {
        "subject": "Re: DFW Lead Packs - Quick Follow Up",
        "body": """Hi [NAME],

Just following up on my email about daily DFW lead packs. I attached a sample from today's run:

- 375 distressed seller leads
- 72 wholesaler/buyer leads

The data pulls automatically every morning from Dallas County public records and verified directories. 

Would a free trial week help you see the value? Just say the word and I'll set it up.

Best,
Mohammed Abdelshafy
"""
    },

    "linkedin_dm": {
        "body": """Hey [NAME],

Saw you're in DFW real estate. I run a daily lead service pulling distressed sellers and wholesalers from public records.

Today's pack: 375 sellers + 72 buyers. All from Dallas 311, KeyCrew, HouseCashin.

Want a free sample? No catch - just reply with your email.
"""
    },

    "facebook_group_post": {
        "body": """Hey DFW real estate fam! 

I built a lead gen system that pulls fresh distressed seller and wholesaler leads every day from:
- Dallas 311 code violations
- KeyCrew verified wholesalers
- HouseCashin directory
- RealEstateBees
- OpenStreetMap

Today's pack: 375 seller leads + 72 buyer leads.

DM me if you want a free sample pack. No strings attached.

#DFWRealEstate #Wholesaling #RealEstateInvesting #LeadGeneration
"""
    }
}

def print_templates():
    print("="*70)
    print("MBM LEAD PACK - AGENCY OUTREACH TEMPLATES")
    print("="*70)
    
    for name, template in TEMPLATES.items():
        print(f"\n{'='*70}")
        print(f"TEMPLATE: {name.upper()}")
        print(f"{'='*70}")
        
        if 'subject' in template:
            print(f"\nSubject: {template['subject']}")
        
        print(f"\n{template['body']}")
        print(f"\n{'='*70}")

if __name__ == "__main__":
    print_templates()
