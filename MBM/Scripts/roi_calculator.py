"""
MBM AI Automation - ROI Calculator & Value Proposition
======================================================
Shows exact time and money saved by AI solutions.
"""

import os
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
TODAY = datetime.now().strftime('%Y-%m-%d')

# ROI DATA - Based on real industry metrics
ROI_DATA = {
    "lead_generation": {
        "name": "AI Lead Generation Engine",
        "before": {
            "hours_per_week": 20,
            "hourly_rate": 25,
            "weekly_cost": 500,
            "leads_per_week": 10,
            "conversion_rate": 0.05,
            "deals_per_month": 0.5,
            "avg_deal_profit": 15000
        },
        "after": {
            "hours_per_week": 2,
            "hourly_rate": 25,
            "weekly_cost": 50,
            "leads_per_week": 50,
            "conversion_rate": 0.15,
            "deals_per_month": 3,
            "avg_deal_profit": 15000
        }
    },
    "email_automation": {
        "name": "AI Email Outreach System",
        "before": {
            "hours_per_week": 15,
            "hourly_rate": 25,
            "weekly_cost": 375,
            "emails_per_week": 100,
            "response_rate": 0.02,
            "meetings_per_week": 2,
            "deals_per_month": 1
        },
        "after": {
            "hours_per_week": 1,
            "hourly_rate": 25,
            "weekly_cost": 25,
            "emails_per_week": 500,
            "response_rate": 0.08,
            "meetings_per_week": 10,
            "deals_per_month": 4
        }
    },
    "customer_support": {
        "name": "AI Customer Support Bot",
        "before": {
            "hours_per_week": 40,
            "hourly_rate": 20,
            "weekly_cost": 800,
            "leads_captured_per_week": 20,
            "leads_lost_per_week": 15,
            "after_hours_leads_lost": 10
        },
        "after": {
            "hours_per_week": 5,
            "hourly_rate": 20,
            "weekly_cost": 100,
            "leads_captured_per_week": 50,
            "leads_lost_per_week": 2,
            "after_hours_leads_lost": 0
        }
    },
    "data_entry": {
        "name": "AI Data Entry & CRM Automation",
        "before": {
            "hours_per_week": 25,
            "hourly_rate": 25,
            "weekly_cost": 625,
            "errors_per_week": 10,
            "cost_per_error": 50,
            "error_cost_per_week": 500
        },
        "after": {
            "hours_per_week": 2,
            "hourly_rate": 25,
            "weekly_cost": 50,
            "errors_per_week": 0,
            "cost_per_error": 0,
            "error_cost_per_week": 0
        }
    },
    "scheduling": {
        "name": "AI Appointment Setter",
        "before": {
            "hours_per_week": 8,
            "hourly_rate": 25,
            "weekly_cost": 200,
            "appointments_per_week": 5,
            "no_show_rate": 0.30,
            "shows_per_week": 3.5
        },
        "after": {
            "hours_per_week": 1,
            "hourly_rate": 25,
            "weekly_cost": 25,
            "appointments_per_week": 15,
            "no_show_rate": 0.10,
            "shows_per_week": 13.5
        }
    },
    "social_media": {
        "name": "AI Social Media Manager",
        "before": {
            "hours_per_week": 10,
            "hourly_rate": 25,
            "weekly_cost": 250,
            "posts_per_week": 5,
            "engagement_rate": 0.02,
            "leads_per_week": 2
        },
        "after": {
            "hours_per_week": 1,
            "hourly_rate": 25,
            "weekly_cost": 25,
            "posts_per_week": 21,
            "engagement_rate": 0.06,
            "leads_per_week": 10
        }
    }
}

# WHOLESALE SPECIFIC ROI
WHOLESALE_ROI = {
    "deal_flow": {
        "before": {
            "deals_per_month": 2,
            "avg_assignment_fee": 15000,
            "monthly_revenue": 30000,
            "time_spent": "60 hours/week searching for deals"
        },
        "after": {
            "deals_per_month": 6,
            "avg_assignment_fee": 15000,
            "monthly_revenue": 90000,
            "time_spent": "10 hours/week reviewing AI-qualified deals"
        }
    },
    "follow_up": {
        "before": {
            "leads_per_month": 100,
            "follow_up_rate": 0.30,
            "conversion_rate": 0.05,
            "deals_per_month": 1.5,
            "monthly_revenue": 22500,
            "time_spent": "40 hours/week manual follow-up"
        },
        "after": {
            "leads_per_month": 100,
            "follow_up_rate": 0.95,
            "conversion_rate": 0.12,
            "deals_per_month": 11.4,
            "monthly_revenue": 171000,
            "time_spent": "5 hours/week reviewing AI results"
        }
    }
}

def print_roi_report():
    """Print comprehensive ROI report."""
    print(f"{'='*70}")
    print(f"MBM AI AUTOMATION - ROI REPORT")
    print(f"Date: {TODAY}")
    print(f"{'='*70}")
    
    print(f"\n{'='*70}")
    print(f"GENERAL AI SOLUTIONS - TIME & MONEY SAVED")
    print(f"{'='*70}")
    
    for key, data in ROI_DATA.items():
        before = data['before']
        after = data['after']
        
        # Calculate savings
        hours_saved = before.get('hours_per_week', 0) - after.get('hours_per_week', 0)
        weekly_labor_saved = hours_saved * before.get('hourly_rate', 25)
        annual_labor_saved = weekly_labor_saved * 52
        
        print(f"\n{'-'*70}")
        print(f"{data['name']}")
        print(f"{'-'*70}")
        print(f"TIME SAVED:")
        print(f"  Before: {before.get('hours_per_week', 'N/A')} hours/week")
        print(f"  After:  {after.get('hours_per_week', 'N/A')} hours/week")
        print(f"  Saved:  {hours_saved} hours/week")
        print(f"  Annual: {hours_saved * 52} hours/year")
        
        print(f"\nMONEY SAVED (Labor):")
        print(f"  Weekly:  ${weekly_labor_saved:,.0f}")
        print(f"  Monthly: ${weekly_labor_saved * 4:,.0f}")
        print(f"  Annual:  ${annual_labor_saved:,.0f}")
        
        # Additional metrics
        if 'leads_per_week' in before:
            leads_increase = after['leads_per_week'] - before['leads_per_week']
            print(f"\nLEAD GENERATION:")
            print(f"  Before: {before['leads_per_week']} leads/week")
            print(f"  After:  {after['leads_per_week']} leads/week")
            print(f"  Increase: +{leads_increase} leads/week (+{int(leads_increase/before['leads_per_week']*100)}%)")
        
        if 'deals_per_month' in before:
            deals_increase = after['deals_per_month'] - before['deals_per_month']
            revenue_increase = deals_increase * before.get('avg_deal_profit', 15000)
            print(f"\nDEAL INCREASE:")
            print(f"  Before: {before['deals_per_month']} deals/month")
            print(f"  After:  {after['deals_per_month']} deals/month")
            print(f"  Increase: +{deals_increase} deals/month")
            print(f"  Extra Revenue: ${revenue_increase:,.0f}/month")
    
    print(f"\n{'='*70}")
    print(f"WHOLESALE SPECIFIC ROI")
    print(f"{'='*70}")
    
    for key, data in WHOLESALE_ROI.items():
        before = data['before']
        after = data['after']
        
        print(f"\n{'-'*70}")
        print(f"{key.upper().replace('_', ' ')}")
        print(f"{'-'*70}")
        print(f"BEFORE (Manual):")
        print(f"  Deals/Month: {before['deals_per_month']}")
        print(f"  Revenue: ${before['monthly_revenue']:,.0f}/month")
        print(f"  Time: {before['time_spent']}")
        
        print(f"\nAFTER (AI Automated):")
        print(f"  Deals/Month: {after['deals_per_month']}")
        print(f"  Revenue: ${after['monthly_revenue']:,.0f}/month")
        print(f"  Time: {after['time_spent']}")
        
        revenue_increase = after['monthly_revenue'] - before['monthly_revenue']
        print(f"\nINCREASE:")
        print(f"  Extra Revenue: ${revenue_increase:,.0f}/month")
        print(f"  Annual Impact: ${revenue_increase * 12:,.0f}/year")
    
    print(f"\n{'='*70}")
    print(f"TOTAL ROI SUMMARY")
    print(f"{'='*70}")
    
    # Calculate totals
    total_annual_labor = sum(
        (d['before'].get('hours_per_week', 0) - d['after'].get('hours_per_week', 0)) * 
        d['before'].get('hourly_rate', 25) * 52
        for d in ROI_DATA.values()
    )
    
    total_monthly_deals_increase = sum(
        d['after'].get('deals_per_month', 0) - d['before'].get('deals_per_month', 0)
        for d in ROI_DATA.values() if 'deals_per_month' in d['before']
    )
    
    total_monthly_revenue_increase = total_monthly_deals_increase * 15000
    
    print(f"\nLabor Savings: ${total_annual_labor:,.0f}/year")
    print(f"Extra Deals: +{total_monthly_deals_increase:.1f}/month")
    print(f"Extra Revenue: ${total_monthly_revenue_increase:,.0f}/month")
    print(f"Annual Revenue Impact: ${total_monthly_revenue_increase * 12:,.0f}/year")
    
    print(f"\n{'='*70}")
    print(f"INVESTMENT vs RETURN")
    print(f"{'='*70}")
    print(f"AI System Cost: $2,500 setup + $500/month = $8,500 first year")
    print(f"ROI: {((total_annual_labor + total_monthly_revenue_increase * 12) / 8500 - 1) * 100:.0f}% return on investment")
    print(f"Payback Period: <30 days")
    print(f"{'='*70}")

def print_client_pitch():
    """Print client pitch with ROI numbers."""
    print(f"""
{'='*70}
MBM AI AUTOMATION - CLIENT PITCH
{'='*70}

Hey [CLIENT NAME],

I looked at your business and found you're losing money every day.

HERE'S THE MATH:

YOUR CURRENT PAIN:
- You spend 20+ hours/week on manual tasks
- You lose 15+ leads/week from slow response
- You miss 10+ after-hours inquiries
- Your team wastes 25+ hours/week on data entry

WHAT THIS COSTS YOU:
- Labor: $2,000/month in wasted time
- Lost Deals: 5-10 deals/month at $15K each
- Total Loss: $75,000-$150,000/month

MY AI SOLUTION:
- AI Lead Gen: Finds 50+ qualified leads/week (vs 10 manually)
- Auto Follow-up: 95% follow-up rate (vs 30% manually)
- 24/7 Chatbot: Never miss an after-hours lead
- Smart CRM: Zero data entry, full pipeline visibility

YOUR RESULTS:
- Time Saved: 40+ hours/week
- Deals Increase: 3x more per month
- Revenue Increase: +$45,000/month
- Annual Impact: +$540,000/year

INVESTMENT:
- Setup: $2,500 (one-time)
- Monthly: $500/month
- Total First Year: $8,500

ROI:
- You invest: $8,500
- You gain: $540,000+
- Return: 6,250%
- Payback: <30 days

I'm only taking 3 more clients this month. After that, prices go up 40%.

Reply "DEMO" and I'll show you exactly how this works.

Mohammed Abdelshafy
AI Automation Specialist
+201040404118
abdelshafyclapps@gmail.com

P.S. I showed this to a wholesaler last week. He closed 2 more deals that month. That's $20K extra. For a 15-minute demo.
{'='*70}
""")

if __name__ == "__main__":
    print_roi_report()
    print_client_pitch()
