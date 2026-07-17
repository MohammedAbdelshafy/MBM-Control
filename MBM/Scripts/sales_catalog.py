"""
MBM Lead Pack Sales Catalog
============================
Pricing and delivery system for selling lead packs to agencies.
"""

CATALOG = """
============================================================
        MBM LEAD PACKS - SALES CATALOG
============================================================

DAILY LEAD PACKS - DFW Metro Area
Sources: Dallas 311, OpenStreetMap, RealEstateBees,
         HouseCashin, KeyCrew, BiggerPockets, Web Directories

============================================================
PACK TYPES
============================================================

1. SELLER LEADS PACK (Distressed Sellers)
   - Code violations, pre-foreclosure signals
   - Property address, owner name, distress signal
   - Daily updated from Dallas 311 Open Data API
   - 300-600+ leads per day

2. BUYER/WHOLESALER LEADS PACK
   - Verified wholesalers, cash buyers, investors
   - Company name, contact info, website
   - Sourced from RealEstateBees, HouseCashin, KeyCrew
   - 50-100+ leads per day

3. FULL PACK (Both)
   - All seller + buyer leads combined
   - 400-700+ leads per day

============================================================
PRICING
============================================================

DAILY SUBSCRIPTION (Auto-delivered email):
  Single Pack (Seller OR Buyer):    $25/day
  Full Pack (Both):                 $40/day
  Weekly (5 days):                  $150/week
  Monthly (22 days):                $500/month

ONE-TIME PURCHASE:
  Single Day Pack:                  $50
  Weekly Bundle:                    $200
  Monthly Bundle:                   $600

CUSTOM PACKS:
  Targeted City (Fort Worth, Arlington, etc.):  +$10/day
  Specific Zip Codes:                            +$15/day
  Phone-Verified Only:                           +$20/day

============================================================
DELIVERY
============================================================

- Email delivery (CSV files)
- Same-day delivery by 9 AM CT
- Each pack includes:
  * Date-stamped CSV file
  * Manifest with source breakdown
  * Confidence scores for each lead

============================================================
SAMPLE DATA
============================================================

Seller Lead:
  Property_Address: 123 Main St, Dallas, TX
  Distress_Signal: Code Violation
  Owner_Name: John Smith
  Confidence: 70%
  Lead_Source: Dallas 311 API

Buyer/Wholesaler Lead:
  Company: New Western
  Website: https://newwestern.com
  City: Dallas, TX
  Confidence: 80%
  Lead_Source: KeyCrew

============================================================
CONTACT TO ORDER
============================================================

Email: abdelshafyclapps@gmail.com
Phone: +201040404118
Payment: Venmo / Zelle / PayPal

============================================================
"""

print(CATALOG)
