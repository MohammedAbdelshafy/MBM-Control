"""
MBM COMPLETE SCRIPT PACKAGE
============================
All scripts, numbers, and info you need to close deals TODAY.

Open: MBM/SCRIPT_PACKAGE.html in your browser for clickable version.
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(r'C:\Users\omare\OneDrive\Desktop\AI\MBM')

# ══════════════════════════════════════════════════════════════
# COLD CALL SCRIPTS FOR PIPELINE DEALS
# ══════════════════════════════════════════════════════════════

PIPELINE_SCRIPTS = [
    {
        "company": "New Western",
        "phone": "(972) 734-1612",
        "email": "sales@newwestern.com",
        "deal_value": "$10,000 - $20,000",
        "solution": "AI Data Entry + Email Automation + Customer Support",
        "last_contact": "Jul 7, 2026",
        "script": {
            "opener": "Hi, this is [YOUR NAME] from MBM Lead Generation. I'm calling to follow up on the AI automation proposal we sent over about a week ago.",
            "value_prop": "We help companies like New Western automate data entry, email outreach, and customer support — saving 20+ hours per week while closing more deals.",
            "proof": "We just helped a DFW wholesale company generate 400+ verified seller leads in 30 days and reduced their email outreach time by 85%.",
            "ask": "I wanted to see if you had 15 minutes this week for a quick Google Meet call to walk through how this would work specifically for New Western?",
            "objection_handlers": {
                "too_busy": "I completely understand — that's actually why this is so valuable. Our automation handles the repetitive work so your team can focus on closing deals. Can I send you a 2-minute video demo instead?",
                "not_interested": "No problem at all. Would it be okay if I sent you a quick case study showing how we helped a similar company increase their deal pipeline by 3x? It's just a 1-page PDF.",
                "need_to_think": "Absolutely, take your time. I'll send you a follow-up email with the ROI calculator so you can see the numbers. When would be a good time to check back in — tomorrow or Thursday?",
                "already_have_solution": "That's great! We actually complement existing tools. Our system feeds verified leads directly into your current CRM. Would it be worth a 10-minute chat to see if there's a fit?",
            }
        }
    },
    {
        "company": "Turner & Partners LLC",
        "phone": "(512) 400-4457",
        "email": "calvin@turnerandpartners.com",
        "deal_value": "$5,000 - $8,000",
        "solution": "AI Data Entry + CRM Automation + Email",
        "last_contact": "Jul 8, 2026",
        "script": {
            "opener": "Hi Calvin, this is [YOUR NAME] from MBM. I'm following up on the CRM automation proposal we sent last week.",
            "value_prop": "We help real estate teams like Turner & Partners automate data entry into your CRM and send personalized email sequences — cutting admin time by 30+ hours per week.",
            "proof": "Our system just helped a Dallas property management company automate 500+ contact updates per week, saving their team 35 hours every week.",
            "ask": "I'd love to show you a quick 10-minute demo of how this would work for Turner & Partners. Would Tuesday or Wednesday work better for you?",
            "objection_handlers": {
                "too_busy": "I hear you — real estate doesn't slow down. That's exactly why automation helps. Our clients get 30 hours back every week. Can I send you a 90-second video instead?",
                "not_interested": "Totally understand. Would you mind if I sent you the ROI breakdown? It shows exactly how much time and money our clients save. No pitch, just numbers.",
                "need_to_think": "Of course. I'll send you a one-pager with the numbers. When should I follow up — end of this week or early next?",
            }
        }
    },
    {
        "company": "PipHouse LLC",
        "phone": "(469) 658-4582",
        "email": "PipHousellc@gmail.com",
        "deal_value": "$3,500 - $5,000",
        "solution": "AI Lead Generation Engine + Email Automation",
        "last_contact": "Jul 7, 2026",
        "script": {
            "opener": "Hi, this is [YOUR NAME] from MBM Lead Generation. I'm calling about the lead generation proposal we sent for PipHouse.",
            "value_prop": "We generate 300+ verified seller leads per month for wholesale companies — at $0.50 per lead compared to $40-$198 with traditional agencies.",
            "proof": "A Dallas wholesaler using our system closed 5 deals in their first month, generating $47,000 in assignment fees.",
            "ask": "Would you have 10 minutes this week for a quick demo? I can show you exactly how many leads we'd generate for PipHouse's target areas.",
            "objection_handlers": {
                "too_busy": "Totally get it. I can send you a 2-minute video demo instead — no call needed. Want me to text it to this number?",
                "not_interested": "No worries. Would it be helpful if I sent you a sample pack of 10 leads for your area so you can see the quality yourself?",
                "need_to_think": "Absolutely. I'll send you a quick email with the sample leads and pricing. When's a good time to check back — Thursday or Friday?",
            }
        }
    },
    {
        "company": "We Buy Houses Fast Dallas",
        "phone": "(469) 461-4209",
        "email": "info@sellmyhousefastindallas.com",
        "deal_value": "$4,000 - $6,000",
        "solution": "AI Customer Support Bot + Email Automation",
        "last_contact": "Jul 7, 2026",
        "script": {
            "opener": "Hi, this is [YOUR NAME] from MBM. I'm following up on the AI customer support proposal we sent last week.",
            "value_prop": "We build AI chatbots that handle inbound leads 24/7 — qualifying sellers, answering questions, and booking appointments while you sleep.",
            "proof": "A cash buyer company in Houston used our bot to respond to 150+ leads per month automatically, increasing their close rate by 40%.",
            "ask": "Would you have 10 minutes for a quick demo? I can show you a live bot working right now.",
            "objection_handlers": {
                "too_busy": "That's actually the point — our bot works when you can't. It responds to every lead within 60 seconds, 24/7. Want to see it in action?",
                "not_interested": "No problem. Would you like me to set up a free trial bot for your website? No cost, no commitment — just see if it works for you.",
                "need_to_think": "Of course. I'll send you a link to a live demo bot you can test yourself. Take a look and let me know what you think.",
            }
        }
    },
    {
        "company": "Swift Home Solutions",
        "phone": "(469) 273-1235",
        "email": "investments@swifthomesolutions.com",
        "deal_value": "$4,000 - $6,000",
        "solution": "AI Email Outreach + Customer Support Bot",
        "last_contact": "Jul 8, 2026",
        "script": {
            "opener": "Hi, this is [YOUR NAME] from MBM. I'm calling about the email automation and support bot proposal we sent.",
            "value_prop": "We automate email outreach to sellers and set up AI bots that qualify leads 24/7 — so your team only talks to motivated sellers.",
            "proof": "We helped a DFW investor send 500+ personalized emails per week and book 15+ appointments per month — all on autopilot.",
            "ask": "Can we set up a 15-minute Google Meet this week? I'll show you the exact system that's working for other DFW investors.",
            "objection_handlers": {
                "too_busy": "I get it — that's why we automate it. Our system does the outreach and qualification so you just show up to appointments. Quick 10-min demo?",
                "not_interested": "Totally fine. Would it be useful if I sent you a template for the exact email sequence that's booking 15+ appointments per month for other investors?",
                "need_to_think": "Sure. I'll send you the email templates and ROI numbers. When should I follow up — next week?",
            }
        }
    },
]

# ══════════════════════════════════════════════════════════════
# TEXT MESSAGE SCRIPTS FOR PRE-FORECLOSURE OWNERS
# ══════════════════════════════════════════════════════════════

TEXT_SCRIPTS = [
    {
        "name": "Harmon Property Services",
        "phone": "(214) 929-7576",
        "properties": "3134 Arizona Ave + 1510 Glen Ave, Dallas",
        "situation": "Carrie Harmon owns BOTH properties, both in foreclosure. She's a contractor.",
        "texts": [
            "Hi Carrie, I'm reaching out about your properties on Arizona Ave and Glen Ave. We have cash buyers ready to close in 7-10 days with zero fees. Are you open to a quick call?",
            "Hi Carrie, I noticed both your Dallas properties are in foreclosure. We can help you get out from under them quickly. Cash offer, no agent fees, we pay closing costs. Can we chat?",
            "Hi, this is regarding 3134 Arizona Ave and 1510 Glen Ave. We work with cash buyers who can close before auction. Would you consider a firm offer? Zero commissions.",
        ]
    },
    {
        "name": "Joel Williams",
        "phone": "(817) 988-8547",
        "properties": "6705 Northland Dr, Fort Worth 76137",
        "situation": "Real estate agent AND investor. Army vet. Lives at property.",
        "texts": [
            "Hi Joel, I see you're a fellow real estate professional. We have off-market distressed properties in DFW with $100K+ equity. Want me to send you the deal sheet?",
            "Hi Joel, we're a property acquisition company in DFW. We have pre-foreclosure deals that might fit your investor portfolio. Can I send you the details?",
            "Hi Joel, fellow agent here. We have 20 verified wholesale properties in DFW. Interested in reviewing them? Cash buyers already matched.",
        ]
    },
    {
        "name": "Mack & Troshane McGuire",
        "phone": "(214) 514-9615",
        "properties": "1825 Canelo Dr, Dallas 75232",
        "situation": "Wells Fargo foreclosure. Auction Aug 4. Age 72-83.",
        "texts": [
            "Hi, I'm reaching out about 1825 Canelo Dr. I see the auction is coming up Aug 4. We have cash buyers who can close before then. Would you consider a firm offer? Zero fees.",
            "Hi, about your property on Canelo Dr — we can help you avoid the auction. Cash offer, close in 7 days, no agent commissions. Would you like to hear more?",
            "Hi, I know the Aug 4 auction is approaching. We work with motivated sellers to get fair cash offers before auction day. Would 10 minutes be enough to discuss options?",
        ]
    },
    {
        "name": "Velma R White",
        "phone": "(817) 366-3324",
        "properties": "1900 Ridge Oak St, Fort Worth 76112",
        "situation": "Age 75, lives at property. Best starter deal in Tarrant County.",
        "texts": [
            "Hi Velma, I'm reaching out about 1900 Ridge Oak St. We're a local home-buying company and would like to make you a fair cash offer. No repairs needed, no fees. Can we chat?",
            "Hi Velma, I hope this message finds you well. We help homeowners in Fort Worth sell quickly without the hassle of listings. Would you be open to hearing a cash offer?",
            "Hi, about Ridge Oak St — we buy houses as-is, close in 7-10 days, and pay all closing costs. Would you like a no-obligation offer?",
        ]
    },
    {
        "name": "Miguel Rodriguez",
        "phone": "(469) 660-3146",
        "properties": "2106 Holland St, Grand Prairie 75051",
        "situation": "Age 37, lives at property. Wells Fargo foreclosure.",
        "texts": [
            "Hi Miguel, I'm reaching out about 2106 Holland St. We have cash buyers who can close in 7 days. Would you entertain a firm offer? Zero agent fees, we pay closing costs.",
            "Hi Miguel, I see the Holland St property is in foreclosure. We can help you sell quickly before auction. Cash offer, no commissions. Can we discuss?",
            "Hi, about your Grand Prairie property — we buy houses as-is, close fast, and cover all costs. Would you like to hear a number?",
        ]
    },
]

# ══════════════════════════════════════════════════════════════
# AGENCY PITCH SCRIPTS
# ══════════════════════════════════════════════════════════════

AGENCY_PITCHES = {
    "cold_call": {
        "opener": "Hi, this is [YOUR NAME] from MBM Lead Generation. We specialize in acquiring and verifying distressed real estate seller leads. I'm calling because we have leads that could feed directly into [AGENCY NAME]'s pipeline.",
        "value_prop": "We pull 300-500 verified seller leads per day from Dallas County public records — code violations, pre-foreclosures, tax delinquents. All with owner name, phone, email, and property address.",
        "pricing": "We sell these in packs: $70 per lead for basic contacts, $150 for verified with phone and email, $300 for premium distressed properties with equity data.",
        "ask": "Would you be interested in a sample pack of 10 leads to test quality? No cost, no commitment.",
    },
    "email_intro": {
        "subject": "DFW Seller Leads - Partnership Opportunity",
        "body": """Hi [CONTACT NAME],

We have 471 verified seller leads available for immediate delivery:

Premium ($300/lead): 209 Dallas distressed sellers
Standard ($150/lead): 40 qualified leads across TX
Base ($70/lead): 202 cash buyer contacts

All verified: phone + email + property address.

Want a free sample of 10 leads?

Best,
MBM Lead Generation""",
    },
}

# ══════════════════════════════════════════════════════════════
# GENERATE HTML SCRIPT PACKAGE
# ══════════════════════════════════════════════════════════════

def generate_html():
    """Generate a clickable HTML script package."""
    html = """<!DOCTYPE html>
<html><head><title>MBM Script Package</title>
<style>
body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
h1 { color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 10px; }
h2 { color: #16213e; margin-top: 30px; }
.card { background: white; border-radius: 10px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
.script { background: #f8f9fa; border-left: 4px solid #e94560; padding: 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }
.script-label { font-weight: bold; color: #e94560; text-transform: uppercase; font-size: 12px; margin-bottom: 5px; }
.phone { font-size: 24px; font-weight: bold; color: #0f3460; }
.btn { display: inline-block; background: #25D366; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 5px; }
.btn-call { background: #0f3460; }
.btn-sms { background: #e94560; }
.deal-value { background: #e8f5e9; padding: 8px 15px; border-radius: 20px; display: inline-block; font-weight: bold; color: #2e7d32; }
.objection { background: #fff3e0; padding: 10px; margin: 5px 0; border-radius: 5px; }
.objection-label { font-weight: bold; color: #e65100; }
.section { margin-bottom: 40px; }
.quick-copy { background: #e3f2fd; padding: 15px; border-radius: 8px; cursor: pointer; border: 2px dashed #1976d2; margin: 10px 0; }
.quick-copy:hover { background: #bbdefb; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
th { background: #16213e; color: white; }
</style>
</head><body>

<h1>MBM Script Package</h1>
<p>Generated: """ + datetime.now().strftime('%B %d, %Y at %I:%M %p') + """</p>

<div class="section">
<h2>PHONE NUMBERS - QUICK DIAL</h2>
<table>
<tr><th>Name</th><th>Phone</th><th>Deal</th><th>Value</th><th>Action</th></tr>
"""
    
    for script in PIPELINE_SCRIPTS:
        phone_digits = script['phone'].replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        html += f"""<tr>
<td><b>{script['company']}</b></td>
<td class="phone">{script['phone']}</td>
<td>{script['solution']}</td>
<td><span class="deal-value">{script['deal_value']}</span></td>
<td>
<a href="tel:{phone_digits}" class="btn btn-call">Call</a>
<a href="sms:{phone_digits}" class="btn btn-sms">Text</a>
</td>
</tr>
"""
    
    html += """</table>
</div>

<div class="section">
<h2>COLD CALL SCRIPTS - PIPELINE DEALS</h2>
"""
    
    for script in PIPELINE_SCRIPTS:
        phone_digits = script['phone'].replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        html += f"""
<div class="card">
<h3>{script['company']} <span class="deal-value">{script['deal_value']}</span></h3>
<p><b>Phone:</b> <a href="tel:{phone_digits}">{script['phone']}</a> | <b>Email:</b> {script['email']}</p>
<p><b>Solution:</b> {script['solution']}</p>
<p><b>Last Contact:</b> {script['last_contact']}</p>

<div class="script">
<div class="script-label">Opener</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{script['script']['opener']}</div>
</div>

<div class="script">
<div class="script-label">Value Proposition</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{script['script']['value_prop']}</div>
</div>

<div class="script">
<div class="script-label">Proof / Case Study</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{script['script']['proof']}</div>
</div>

<div class="script">
<div class="script-label">The Ask</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{script['script']['ask']}</div>
</div>

<h4>Objection Handlers:</h4>
"""
        for obj, handler in script['script']['objection_handlers'].items():
            html += f"""<div class="objection">
<span class="objection-label">"{obj.replace('_', ' ').title()}":</span> {handler}
</div>
"""
        html += "</div>"
    
    html += """</div>

<div class="section">
<h2>TEXT MESSAGE SCRIPTS - PRE-FORECLOSURE OWNERS</h2>
"""
    
    for script in TEXT_SCRIPTS:
        phone_digits = script['phone'].replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        html += f"""
<div class="card">
<h3>{script['name']} <span class="deal-value">{script['properties']}</span></h3>
<p><b>Phone:</b> <a href="tel:{phone_digits}">{script['phone']}</a></p>
<p><b>Properties:</b> {script['properties']}</p>
<p><b>Situation:</b> {script['situation']}</p>

<h4>Text Options (click to copy):</h4>
"""
        for i, text in enumerate(script['texts'], 1):
            html += f"""<div class="script">
<div class="script-label">Text #{i}</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{text}</div>
<a href="sms:{phone_digits}?body={text.replace(' ', '%20')}" class="btn btn-sms">Send This Text</a>
</div>
"""
        html += "</div>"
    
    html += """</div>

<div class="section">
<h2>AGENCY PITCH SCRIPTS</h2>

<div class="card">
<h3>Cold Call Script - Lead Gen Agencies</h3>
"""
    
    for key, val in AGENCY_PITCHES['cold_call'].items():
        html += f"""<div class="script">
<div class="script-label">{key.replace('_', ' ').title()}</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{val}</div>
</div>
"""
    
    html += f"""</div>

<div class="card">
<h3>Email Template - Agency Outreach</h3>
<div class="script">
<div class="script-label">Subject</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{AGENCY_PITCHES['email_intro']['subject']}</div>
</div>
<div class="script">
<div class="script-label">Body</div>
<div class="quick-copy" onclick="navigator.clipboard.writeText(this.innerText)">{AGENCY_PITCHES['email_intro']['body']}</div>
</div>
</div>
</div>

<div class="section">
<h2>TODAY'S REVENUE POTENTIAL</h2>
<div class="card">
<table>
<tr><th>Opportunity</th><th>Revenue</th><th>Action</th></tr>
<tr><td>New Western closes</td><td>$10,000 - $20,000</td><td>Call (972) 734-1612</td></tr>
<tr><td>Turner & Partners closes</td><td>$5,000 - $8,000</td><td>Call (512) 400-4457</td></tr>
<tr><td>PipHouse closes</td><td>$3,500 - $5,000</td><td>Call (469) 658-4582</td></tr>
<tr><td>1 Wholesale deal</td><td>$10,000 - $25,000</td><td>Text pre-foreclosure owners</td></tr>
<tr><td>1 Lead pack sale</td><td>$70 - $300 per lead</td><td>Post on marketplaces</td></tr>
<tr><td>1 Agency partnership</td><td>$500 - $2,000/mo</td><td>Telegram outreach sent</td></tr>
<tr><th>TOTAL POTENTIAL</th><th>$30,000+</th><th></th></tr>
</table>
</div>
</div>

<div class="section">
<h2>LEAD PACKS AVAILABLE</h2>
<div class="card">
<table>
<tr><th>Pack</th><th>Tier</th><th>Leads</th><th>Price</th><th>Total</th></tr>
<tr><td>Dallas Distressed Seller</td><td>Premium</td><td>209</td><td>$300/lead</td><td>$62,700</td></tr>
<tr><td>DFW Wholesale Deal</td><td>Premium</td><td>20</td><td>$300/lead</td><td>$6,000</td></tr>
<tr><td>Multi-Market Qualified</td><td>Mid</td><td>40</td><td>$150/lead</td><td>$6,000</td></tr>
<tr><td>Cash Buyer Contact</td><td>Base</td><td>202</td><td>$70/lead</td><td>$14,140</td></tr>
<tr><th>TOTAL</th><th></th><th>471</th><th></th><th>$88,840</th></tr>
</table>
</div>
</div>

<p style="text-align:center; color:#666; margin-top:40px;">
Generated by MBM Lead Generation Engine<br>
All scripts are ready to use — click any box to copy
</p>

</body></html>"""
    
    return html


if __name__ == '__main__':
    # Generate HTML
    html = generate_html()
    html_file = BASE_DIR / 'SCRIPT_PACKAGE.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Script package created: {html_file}")
    
    # Open in browser
    import subprocess
    subprocess.Popen(['start', str(html_file)], shell=True)
