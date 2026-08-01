#!/usr/bin/env python3
"""
MBM Lead Scripts - Personalized call scripts for every lead
"""

LEAD_SCRIPTS = {
    "+14696584582": {
        "name": "PipHouse LLC",
        "company": "PipHouse LLC",
        "contact": "PipHousellc@gmail.com",
        "value": "$3,500-5,000",
        "solution": "AI Lead Generation Engine + Email Automation",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to PipHouse LLC.

We spoke about implementing an AI Lead Generation Engine and Email Automation system for your wholesale business.

I wanted to follow up - are you still interested in moving forward with this?

[IF YES]
Great! We can generate 300+ verified seller leads per month for your business. The system automatically enriches leads, scores them by motivation level, and sends personalized outreach.

What's your timeline for getting started? We can have a demo ready this week.

[IF NO]
No problem at all. If your needs change, we're here to help. Can I ask what changed?

[IF BUSY]
I understand you're busy. When would be a better time for a quick 10-minute call to discuss this?""",
        "objections": {
            "too_expensive": "I understand budget is a concern. Our system actually pays for itself within the first week - 300 leads at $0.50 each means you're paying $150 for leads that would cost $3,000+ on Zillow or other platforms.",
            "already_have_leads": "That's great! Many of our clients already had lead sources. Our system adds a second channel that runs 24/7 without any manual work. It's about volume and consistency.",
            "need_to_think": "Of course. Take your time. I'll follow up next Tuesday. In the meantime, I can send you a case study of how we helped another Dallas wholesaler close 12 deals in their first month."
        }
    },

    "+14692731235": {
        "name": "Swift Home Solutions",
        "company": "Swift Home Solutions",
        "contact": "investments@swifthomesolutions.com",
        "value": "$4,000-6,000",
        "solution": "AI Email Outreach + Customer Support Bot",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to Swift Home Solutions.

We proposed an AI Email Outreach system and Customer Support Bot to help streamline your operations.

Are you still interested in automating your email outreach and customer support?

[IF YES]
Excellent! Our AI Email system sends personalized outreach to 500+ prospects per day, and the Customer Support Bot handles common questions 24/7.

What's your biggest pain point right now - is it lead response time or email volume?

[IF NO]
I understand. What's changed since we last spoke? Maybe there's a different solution that would work better for you.

[IF ALREADY USING SOMETHING]
That's great! Are you happy with the results? Our system integrates with most platforms and can enhance what you already have.""",
        "objections": {
            "too_many_emails": "I hear you. Our system actually reduces email volume by sending only to pre-qualified leads. You get fewer but better emails.",
            "tried_before": "Many of our clients tried other solutions first. What makes ours different is the AI scoring - it only emails people who are actually motivated to sell.",
            "budget_constraints": "I understand. Let's look at ROI - if our system helps you close just one extra deal per month, that's $10,000+ in revenue for a $4,000 investment."
        }
    },

    "+19727341612": {
        "name": "New Western",
        "company": "New Western",
        "contact": "sales@newwestern.com",
        "value": "$10,000-20,000",
        "solution": "AI Data Entry + Email Automation + Customer Support",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to New Western's sales team.

We proposed an AI Data Entry system, Email Automation, and Customer Support solution to help streamline your acquisitions process.

Are you still looking to automate data entry and improve your email workflow?

[IF YES]
Great! New Western is one of the biggest wholesalers in DFW. Our system can handle property data entry, automate follow-ups, and provide 24/7 customer support.

What's your current data entry volume? We can show you exactly how much time and money you'd save.

[IF NO]
No problem. I know New Western has a large operation. What's your biggest operational challenge right now? Maybe we can help in a different way.

[IF TRANSFERRED TO SOMEONE ELSE]
Hi, I'm following up on a proposal we sent about AI automation for your acquisitions team. Do you have a moment?""",
        "objections": {
            "already_have_team": "That's great! Our system doesn't replace your team - it frees them up from repetitive data entry so they can focus on closing deals. Think of it as giving each team member an AI assistant.",
            "too_big_to_automate": "Actually, that's exactly why automation helps. The bigger the operation, the more time and money you save. We've helped companies with 50+ employees automate their workflows.",
            "need_approval": "Of course. Would it help if I sent you an ROI report you can present to decision-makers? We can customize it for New Western's specific needs."
        }
    },

    "+18173001132": {
        "name": "DFW REI Club",
        "company": "DFW REI Club",
        "contact": "robin@dfwrei.com",
        "value": "$2,500-4,000",
        "solution": "AI Email Automation + Social Media Manager",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to Robin at DFW REI Club.

We proposed an AI Email Automation system and Social Media Manager to help grow your real estate investing community.

Are you still interested in automating your email campaigns and social media presence?

[IF YES]
Excellent! Our AI can send personalized emails to your member list, post engaging content on social media, and even respond to member inquiries automatically.

What's your biggest challenge right now - member engagement or lead generation?

[IF NO]
I understand. What's changed? Maybe we can adjust the solution to better fit your current needs.

[IF ALREADY DOING IT]
That's great! Are you getting the results you want? Our system can enhance what you're doing and free up your time.""",
        "objections": {
            "social_media_automated": "That's good! Our AI goes beyond scheduling - it creates engaging content, responds to comments, and grows your following organically. It's like having a full-time social media manager.",
            "email_open_rates_low": "That's exactly what our AI fixes. It personalizes every email based on the recipient's interests and behavior. Our clients see 3x higher open rates.",
            "budget": "I understand. Let's look at the numbers - if our system helps you get just 10 more members per month at $50/month, that's $500 in additional revenue for a $2,500 investment."
        }
    },

    "+12149297576": {
        "name": "Property Owner - 3134 Arizona Ave",
        "company": "Individual Seller",
        "contact": "Phone only",
        "value": "Cash Offer",
        "solution": "Pre-foreclosure acquisition",
        "script": """Hi, this is Maria from MBM Property Solutions. I'm reaching out about your property at 3134 Arizona Ave in Dallas.

We have cash buyers who are ready to close in 7-10 days with zero fees. Are you open to hearing about a cash offer?

[IF YES]
Great! Can I ask a few quick questions?
- What's your timeline for selling?
- Are there any liens or issues with the property?
- What's your ideal price?

We can have someone at your property within 24 hours for a no-obligation walkthrough.

[IF NO]
No problem. If you ever need to sell quickly, we're here to help. Can I keep your information on file?

[IF ALREADY SOLD]
Congratulations! If you need help buying another property, we'd love to assist.""",
        "objections": {
            "need_more_time": "Of course. Take your time. When would be a good time to check back in?",
            "trying_other_options": "That's completely fine. Most of our clients tried other options first. We're here as a backup if those don't work out.",
            "price_too_low": "I understand. Let me explain - our cash offers are competitive because we close fast and cover all closing costs. No repairs needed, no agent commissions."
        }
    },

    "+18179888547": {
        "name": "Joel - RE Agent/Investor",
        "company": "Joel - Real Estate Agent",
        "contact": "Phone only",
        "value": "Partnership",
        "solution": "Off-market deal flow",
        "script": """Hi Joel, this is Sarah from MBM Property Solutions. I saw you're a real estate agent and investor in the DFW area.

We have off-market distressed properties in DFW with $100K+ equity. Would you be interested in receiving our deal sheets?

[IF YES]
Great! We send out weekly deal sheets with:
- Property addresses and photos
- Estimated ARV and repair costs
- Cash buyer pricing
- Timeline to close

What's the best email to send these to?

[IF NO]
No problem. If you ever need off-market deals, we're here to help. Can I keep your information?

[IF ALREADY HAVE SOURCES]
That's great! Our deals are exclusive - not on MLS or Zillow. We typically have 5-10 deals per month that other wholesalers don't see.""",
        "objections": {
            "already_have_dealers": "That's good! Our deals are exclusive off-market properties. Many agents use us as a second source when their regular dealers don't have what they need.",
            "need_to_see_deals": "Of course! Let me send you this week's deal sheet. If you like what you see, we can set up automatic weekly sends.",
            "not_buying_right_now": "No problem. When you're ready to buy, we'll have deals waiting. Can I send you our newsletter so you stay updated?"
        }
    },

    "+12145149615": {
        "name": "Property Owner - 1825 Canelo Dr",
        "company": "Individual Seller",
        "contact": "Phone only",
        "value": "Cash Offer",
        "solution": "Pre-foreclosure acquisition",
        "script": """Hi, this is Maria from MBM Property Solutions. I'm reaching out about your property at 1825 Canelo Dr.

We have cash buyers who can close before the August 4th auction. Would you consider a firm offer? Zero agent fees, we pay all closing costs.

[IF YES]
Great! Can I ask a few quick questions?
- When is your auction date?
- How much do you owe on the mortgage?
- Would you accept a cash offer below market value?

We can have someone at your property today for a walkthrough.

[IF NO]
I understand. If things change before the auction, we're here to help. Can I keep your information on file?

[IF ALREADY SOLD]
That's great! Congratulations on resolving the situation.""",
        "objections": {
            "auction_too_soon": "I understand the timeline is tight. That's actually why we can help - we close in 72 hours, which is fast enough to stop the auction.",
            "owe_too_much": "Let me look at the numbers. Even if you owe more than the property is worth, we might be able to negotiate a short sale with the bank. Let me check.",
            "trying_loan_mod": "That's a good option if it works. But if it doesn't come through before the auction, we're here as a backup. Can I check back in a week?"
        }
    },

    "+18173663324": {
        "name": "Velma - 1900 Ridge Oak St",
        "company": "Individual Seller",
        "contact": "Phone only",
        "value": "Cash Offer",
        "solution": "Pre-foreclosure acquisition",
        "script": """Hi Velma, this is Maria from MBM Property Solutions. I'm reaching out about your property at 1900 Ridge Oak St.

We'd like to make a cash offer before the auction. Can we chat for 5 minutes?

[IF YES]
Thank you for your time. I have a few quick questions:
- What's your timeline for selling?
- Are there any issues with the property?
- What's your ideal price?

We can close in 72 hours with cash. No repairs needed, no agent commissions.

[IF NO]
I understand you're busy. When would be a better time for a quick 5-minute call? We can help stop the auction.

[IF ALREADY RESOLVED]
That's wonderful! I'm glad you were able to work it out.""",
        "objections": {
            "dont_want_to_sell": "I understand. But if the auction happens, the bank takes the property and you lose all equity. A cash sale lets you walk away with money in your pocket.",
            "need_to_talk_to_family": "Of course. This is a big decision. When can we all sit down together? We can answer any questions.",
            "price_concerns": "Let me explain - our offers are fair because we close fast and take the property as-is. No repairs, no waiting, no uncertainty."
        }
    },

    "+14696603146": {
        "name": "Miguel - 2106 Holland St",
        "company": "Individual Seller",
        "contact": "Phone only",
        "value": "Cash Offer",
        "solution": "Pre-foreclosure acquisition",
        "script": """Hi Miguel, this is Maria from MBM Property Solutions. I'm reaching out about your property at 2106 Holland St.

We can close in 7 days with cash. Would you entertain a firm offer?

[IF YES]
Great! Can I ask a few quick questions?
- What's your timeline?
- Are there any liens or issues?
- What's your asking price?

We pay all closing costs and handle all paperwork.

[IF NO]
No problem. If you ever need to sell quickly, we're here. Can I keep your information?

[IF ALREADY SOLD]
Congratulations! If you need help with anything else, don't hesitate to reach out.""",
        "objections": {
            "need_more_money": "I understand. Let me explain our pricing - we offer fair market value minus repair costs. Since we close fast and take as-is, you save thousands in repairs and holding costs.",
            "trying_realtor": "That's an option. But realtors take 6% commission, require repairs, and take 60-90 days to close. We close in 7 days with no fees.",
            "not_sure": "Take your time. I'll follow up next week. In the meantime, if you have any questions, call me anytime."
        }
    },

    "+14694364884": {
        "name": "Diamond Acquisitions",
        "company": "Diamond Acquisitions",
        "contact": "diamondacquisitions@outlook.com",
        "value": "Partnership",
        "solution": "AI Lead Generation",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to Diamond Acquisitions.

We sent you information about AI Lead Generation for your wholesale business. Our system generates 300+ verified leads per month at $0.50/lead.

Are you still interested in scaling your lead generation?

[IF YES]
Great! Our system:
- Generates 300+ leads per month
- Enriches with phone, email, and property data
- Scores leads by motivation level
- Sends personalized outreach automatically

What's your current lead volume? We can show you exactly how much you'd grow.

[IF NO]
No problem. What's your biggest challenge right now? Maybe we can help differently.

[IF ALREADY HAVE SYSTEM]
That's great! Is it working well? Our system can complement what you have and add a second lead source.""",
        "objections": {
            "already_have_leads": "Good! Many of our clients use multiple lead sources. Our system adds consistency - it runs 24/7 and never takes a day off.",
            "budget": "I understand. Let's look at ROI - 300 leads at $150/month means you're paying $0.50 per lead. If just 1% convert, that's 3 deals per month.",
            "need_to_see_demo": "Of course! I can set up a live demo this week. You'll see exactly how the system works with real data."
        }
    },

    "+15124004457": {
        "name": "Calvin - Turner & Partners",
        "company": "Turner & Partners",
        "contact": "Phone only",
        "value": "Partnership",
        "solution": "AI Data Entry + CRM",
        "script": """Hi Calvin, this is Sarah from MBM Property Solutions. I'm following up on the AI Data Entry + CRM proposal for Turner & Partners.

We can save your team 30+ hours per week by automating data entry and CRM updates.

Are you still looking to streamline your operations?

[IF YES]
Great! Our AI automatically:
- Enters property data from public records
- Updates CRM with lead information
- Sends follow-up emails
- Generates reports

What's your team's biggest time sink right now?

[IF NO]
I understand. What's changed? Maybe there's a different solution that would work better.

[IF ALREADY AUTOMATED]
That's great! Are you getting the results you want? Our system can enhance what you already have.""",
        "objections": {
            "team_can_handle": "That's good! But think about what they could do with 30 extra hours per week. They could close more deals instead of entering data.",
            "too_complex": "Actually, it's simple. We set it up, train your team in 30 minutes, and it runs automatically. No technical skills needed.",
            "need_to_think": "Of course. Let me send you an ROI report so you can see the numbers. We can discuss next week."
        }
    },

    "+14694614209": {
        "name": "DFW Investor",
        "company": "DFW Real Estate Investor",
        "contact": "Phone only",
        "value": "Partnership",
        "solution": "AI Customer Support + Email",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out about AI Customer Support and Email Automation for your investment business.

We help DFW investors close 3x more deals by automating follow-ups and customer support.

Are you interested in a quick demo this week?

[IF YES]
Excellent! Our system:
- Responds to leads within 5 minutes (24/7)
- Sends personalized follow-ups
- Handles customer questions automatically
- Books appointments directly

What's your current lead response time? Most investors lose deals because they respond too slowly.

[IF NO]
No problem. What's your biggest challenge right now? Maybe we can help differently.

[IF ALREADY HAVE SYSTEM]
That's great! Is it working well? Our system can fill the gaps and add more automation.""",
        "objections": {
            "already_have_crm": "Good! Our AI works WITH your CRM. It automates the follow-ups and responses that your CRM can't do.",
            "budget": "I understand. Let's look at ROI - if our system helps you close just 1 extra deal per month, that's $10,000+ in revenue.",
            "need_to_see_demo": "Of course! I can set up a live demo this week. You'll see exactly how it works."
        }
    },

    "+12142841222": {
        "name": "Rylie - Altura Homes",
        "company": "Altura Homes",
        "contact": "rylie@alturahomes.com",
        "value": "Partnership",
        "solution": "AI Lead Generation",
        "script": """Hi Rylie, this is Sarah from MBM Property Solutions. We found your email via alturahomes.com.

We help builders and investors generate 500+ qualified leads per month.

Are you interested in scaling your lead generation?

[IF YES]
Great! Our system generates leads specifically for builders and investors like you. We can target:
- Homeowners looking to sell
- Pre-foreclosure properties
- Off-market deals
- Cash buyers

What's your current lead volume? We can show you how to double it.

[IF NO]
No problem. What's your biggest challenge right now? Maybe we can help differently.

[IF ALREADY HAVE LEADS]
That's great! Our system adds a second source. More leads = more deals.""",
        "objections": {
            "already_have_leads": "Good! More leads means more deals. Our system runs 24/7 and finds deals your current sources miss.",
            "budget": "I understand. Let's look at ROI - 500 leads at $250/month means $0.50 per lead. If just 1% convert, that's 5 deals.",
            "need_to_think": "Of course. Let me send you a case study of how we helped another builder close 15 deals in their first month."
        }
    },

    "+12149089188": {
        "name": "Steve Hendry Homes",
        "company": "Steve Hendry Homes / RE/MAX",
        "contact": "stevehendry@remax.net",
        "value": "Partnership",
        "solution": "AI Lead Generation + CRM",
        "script": """Hi Steve, this is Sarah from MBM Property Solutions. I'm reaching out about AI Lead Generation and CRM automation for your real estate business.

We help agents and investors generate more leads and close more deals.

Are you interested in scaling your business?

[IF YES]
Great! Our system:
- Generates 300+ leads per month
- Automates follow-ups
- Manages your CRM
- Books appointments automatically

What's your biggest challenge right now - lead generation or lead conversion?

[IF NO]
No problem. What's your current focus? Maybe we can help differently.

[IF ALREADY BUSY]
That's great! Our system can handle the overflow and make sure no lead falls through the cracks.""",
        "objections": {
            "already_have_leads": "Good! Our system adds consistency. It runs 24/7 and never takes a day off. More leads = more deals.",
            "budget": "I understand. Let's look at ROI - if our system helps you close just 1 extra deal per month, that's $10,000+ in commission.",
            "need_to_think": "Of course. Let me send you a case study of how we helped another RE/MAX agent close 8 deals in their first month."
        }
    },

    "+12142336158": {
        "name": "ULR Properties - Dallas",
        "company": "ULR Properties",
        "contact": "Phone only",
        "value": "Partnership",
        "solution": "AI Lead Generation",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to ULR Properties about AI Lead Generation for your Dallas operations.

We help property companies generate more qualified leads and close more deals.

Are you interested in scaling your lead generation?

[IF YES]
Great! Our system generates leads specifically for property companies. We can target:
- Homeowners looking to sell
- Pre-foreclosure properties
- Off-market deals
- Cash buyers

What's your current lead volume? We can show you how to double it.

[IF NO]
No problem. What's your biggest challenge right now? Maybe we can help differently.""",
        "objections": {
            "already_have_leads": "Good! Our system adds a second source. More leads = more deals. It runs 24/7 and finds deals your current sources miss.",
            "budget": "I understand. Let's look at ROI - 300 leads at $150/month means $0.50 per lead. If just 1% convert, that's 3 deals.",
            "need_to_think": "Of course. Let me send you a case study of how we helped another property company close 10 deals in their first month."
        }
    },

    "+12145998997": {
        "name": "LBJ Station",
        "company": "LBJ Station",
        "contact": "Phone only",
        "value": "Partnership",
        "solution": "AI Lead Generation + Marketing",
        "script": """Hi, this is Sarah from MBM Property Solutions. I'm reaching out to LBJ Station about AI Lead Generation and Marketing automation.

We help property companies generate more leads and automate their marketing.

Are you interested in scaling your business?

[IF YES]
Great! Our system:
- Generates 300+ leads per month
- Automates email marketing
- Manages social media
- Books appointments automatically

What's your biggest challenge right now - lead generation or marketing?

[IF NO]
No problem. What's your current focus? Maybe we can help differently.""",
        "objections": {
            "already_have_marketing": "Good! Our AI enhances what you have. It personalizes every message and runs 24/7.",
            "budget": "I understand. Let's look at ROI - if our system helps you close just 1 extra deal per month, that's $10,000+ in revenue.",
            "need_to_think": "Of course. Let me send you a case study of how we helped another property company close 8 deals in their first month."
        }
    }
}


def get_script(phone):
    """Get the call script for a phone number"""
    # Normalize phone number
    phone = phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if not phone.startswith("+"):
        phone = "+1" + phone

    return LEAD_SCRIPTS.get(phone, {
        "name": "Unknown Lead",
        "company": "Unknown",
        "script": "Hi, this is Sarah from MBM Property Solutions. Are you still interested in our services?",
        "objections": {}
    })


if __name__ == "__main__":
    import json
    print(json.dumps(LEAD_SCRIPTS, indent=2))
