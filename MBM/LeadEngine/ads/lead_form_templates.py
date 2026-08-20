"""
Lead Form Templates for Facebook Ads & Google Ads
===================================================
Pre-built lead form configurations for three service verticals:
  1. AI Consultancy Discovery
  2. Website Project Inquiry
  3. App Development Brief

Each template works with both Facebook Lead Ads and Google Lead Form Extensions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class LeadFormField:
    """Single field in a lead form."""
    key: str
    label: str
    field_type: str = "TEXT"  # TEXT, EMAIL, PHONE, SELECT, TEXTAREA
    required: bool = True
    options: List[str] = field(default_factory=list)  # For SELECT type
    prefill_from: str = ""  # Facebook/Google prefill key (e.g., "FULL_NAME")


@dataclass
class LeadFormTemplate:
    """Complete lead form template for both platforms."""
    name: str
    headline: str
    description: str
    privacy_policy_url: str = "https://moaiza.com/privacy"
    thank_you_headline: str = "Thank You!"
    thank_you_description: str = "We'll be in touch within 24 hours."
    thank_you_cta_text: str = "Visit Our Website"
    thank_you_cta_url: str = "https://moaiza.com"
    fields: List[LeadFormField] = field(default_factory=list)
    vertical: str = ""

    def to_facebook_format(self) -> Dict[str, Any]:
        """Convert to Facebook Lead Ad form spec."""
        questions = []
        for f in self.fields:
            q: Dict[str, Any] = {"key": f.key, "label": f.label}
            if f.field_type == "SELECT" and f.options:
                q["type"] = "CUSTOM"
                q["options"] = [{"value": o, "key": o.lower().replace(" ", "_")} for o in f.options]
            elif f.field_type == "EMAIL":
                q["type"] = "EMAIL"
            elif f.field_type == "PHONE":
                q["type"] = "PHONE"
            elif f.field_type == "TEXTAREA":
                q["type"] = "CUSTOM"
            else:
                q["type"] = "CUSTOM" if not f.prefill_from else f.prefill_from
            questions.append(q)

        return {
            "name": self.name,
            "locale": "EN_US",
            "follow_up_action_url": self.thank_you_cta_url,
            "context_card": {
                "title": self.headline,
                "content": [self.description],
                "style": "PARAGRAPH_STYLE",
            },
            "thank_you_page": {
                "title": self.thank_you_headline,
                "body": self.thank_you_description,
                "button_text": self.thank_you_cta_text,
                "button_type": "VIEW_WEBSITE",
                "website_url": self.thank_you_cta_url,
            },
            "questions": questions,
            "privacy_policy": {"url": self.privacy_policy_url, "link_text": "Privacy Policy"},
        }

    def to_google_format(self) -> Dict[str, Any]:
        """Convert to Google Ads Lead Form Extension spec."""
        fields_map = {
            "EMAIL": "LEAD_FORM_FIELD_TYPE_EMAIL",
            "PHONE": "LEAD_FORM_FIELD_TYPE_PHONE_NUMBER",
            "TEXT": "LEAD_FORM_FIELD_TYPE_FULL_NAME",
        }
        lead_form_fields = []
        for f in self.fields:
            if f.field_type in fields_map:
                lead_form_fields.append({"input_type": fields_map[f.field_type]})
            # Custom questions for SELECT and TEXTAREA
            elif f.field_type in ("SELECT", "TEXTAREA"):
                lead_form_fields.append({
                    "input_type": "LEAD_FORM_FIELD_TYPE_CUSTOM_QUESTION",
                    "single_choice_answers": {
                        "answers": f.options
                    } if f.field_type == "SELECT" else None,
                })

        return {
            "headline": self.headline,
            "description": self.description,
            "business_name": "MOAIZA AI",
            "call_to_action_type": "GET_QUOTE",
            "call_to_action_description": self.thank_you_description,
            "privacy_policy_url": self.privacy_policy_url,
            "post_submit_headline": self.thank_you_headline,
            "post_submit_description": self.thank_you_description,
            "post_submit_call_to_action_type": "VISIT_SITE",
            "fields": lead_form_fields,
        }


# ── Pre-built Templates ────────────────────────────────────────────────────

AI_CONSULTANCY_FORM = LeadFormTemplate(
    name="AI Consultancy Discovery",
    headline="Free AI Strategy Session — Save 20+ Hours/Week",
    description=(
        "Find out how AI can automate your business operations, "
        "cut costs, and accelerate growth. Book a free 15-minute discovery call."
    ),
    thank_you_headline="You're In! 🎯",
    thank_you_description="Our AI strategist will reach out within 24 hours to schedule your session.",
    vertical="ai_consultancy",
    fields=[
        LeadFormField(key="full_name", label="Full Name", prefill_from="FULL_NAME"),
        LeadFormField(key="email", label="Business Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="phone", label="Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="company", label="Company Name"),
        LeadFormField(
            key="business_type", label="What type of business do you run?",
            field_type="SELECT",
            options=[
                "Agency / Consultancy",
                "E-commerce / Retail",
                "Real Estate",
                "Healthcare / Medical",
                "SaaS / Tech Startup",
                "Construction / Engineering",
                "Other",
            ],
        ),
        LeadFormField(
            key="ai_interest", label="What would you like AI to help with?",
            field_type="SELECT",
            options=[
                "Lead Generation & Sales",
                "Customer Support Chatbot",
                "Process Automation",
                "Data Analysis & Insights",
                "Content Creation",
                "Not sure yet — need advice",
            ],
        ),
    ],
)

WEBSITE_PROJECT_FORM = LeadFormTemplate(
    name="Website Project Inquiry",
    headline="Get a Professional Website Built in 14 Days",
    description=(
        "Custom-designed, mobile-responsive websites that convert visitors "
        "into customers. No templates — fully bespoke designs."
    ),
    thank_you_headline="Great Choice! 🚀",
    thank_you_description="Our design team will send you a project brief within 24 hours.",
    vertical="website_creation",
    fields=[
        LeadFormField(key="full_name", label="Full Name", prefill_from="FULL_NAME"),
        LeadFormField(key="email", label="Business Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="phone", label="Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="company", label="Company / Brand Name"),
        LeadFormField(
            key="website_type", label="What type of website do you need?",
            field_type="SELECT",
            options=[
                "Business / Corporate Website",
                "E-commerce Store",
                "Landing Page / Sales Funnel",
                "Portfolio / Personal Brand",
                "Booking / Appointment Platform",
                "Web Application (SaaS)",
                "Other",
            ],
        ),
        LeadFormField(
            key="budget_range", label="Approximate budget range?",
            field_type="SELECT",
            options=[
                "Under $1,000",
                "$1,000 – $3,000",
                "$3,000 – $7,000",
                "$7,000 – $15,000",
                "$15,000+",
            ],
        ),
    ],
)

APP_DEVELOPMENT_FORM = LeadFormTemplate(
    name="App Development Brief",
    headline="Turn Your App Idea Into Reality",
    description=(
        "iOS, Android, or cross-platform — we build high-performance mobile apps "
        "with AI-powered features. From concept to App Store in 8–12 weeks."
    ),
    thank_you_headline="Exciting! 📱",
    thank_you_description="Our product lead will schedule a discovery call within 24 hours.",
    vertical="app_creation",
    fields=[
        LeadFormField(key="full_name", label="Full Name", prefill_from="FULL_NAME"),
        LeadFormField(key="email", label="Business Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="phone", label="Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="company", label="Company Name", required=False),
        LeadFormField(
            key="platform", label="Target platform?",
            field_type="SELECT",
            options=[
                "iOS (iPhone / iPad)",
                "Android",
                "Both iOS & Android",
                "Web App (PWA)",
                "Not sure yet",
            ],
        ),
        LeadFormField(
            key="app_stage", label="Where are you in the process?",
            field_type="SELECT",
            options=[
                "Just an idea",
                "Have wireframes / mockups",
                "Have a prototype / MVP",
                "Need to rebuild existing app",
                "Need new features added",
            ],
        ),
        LeadFormField(
            key="budget_range", label="Approximate budget range?",
            field_type="SELECT",
            options=[
                "Under $5,000",
                "$5,000 – $15,000",
                "$15,000 – $30,000",
                "$30,000 – $75,000",
                "$75,000+",
            ],
        ),
    ],
)

REAL_ESTATE_SELLER_FORM = LeadFormTemplate(
    name="Motivated Seller Property Evaluation",
    headline="Get a Fair As-Is Cash Offer in 24 Hours",
    description="No repairs needed, no agent fees, close on your timeline. Get a free confidential property evaluation.",
    thank_you_headline="Offer In Progress! 🏡",
    thank_you_description="Our property specialist will review county comps and reach out with your cash valuation.",
    vertical="real_estate_sellers",
    fields=[
        LeadFormField(key="full_name", label="Full Name", prefill_from="FULL_NAME"),
        LeadFormField(key="phone", label="Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="email", label="Email Address", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="property_address", label="Property Address"),
        LeadFormField(
            key="selling_timeline", label="How soon do you need to sell?",
            field_type="SELECT",
            options=["Immediately (< 14 days)", "1-2 Months", "3-6 Months", "Just exploring options"],
        ),
        LeadFormField(
            key="property_condition", label="Property condition?",
            field_type="SELECT",
            options=["Move-in Ready", "Needs Minor Repairs", "Needs Major Renovation", "Total Teardown"],
        ),
    ],
)

CASH_BUYER_FORM = LeadFormTemplate(
    name="VIP Cash Buyer & Investor Application",
    headline="Access Off-Market Distressed Deals at 40-60% ARV",
    description="Join our exclusive buyers list for verified off-market residential and commercial properties.",
    thank_you_headline="Application Received! 💼",
    thank_you_description="Our acquisitions desk will approve your profile and deliver matching deals.",
    vertical="cash_buyers",
    fields=[
        LeadFormField(key="full_name", label="Full Name", prefill_from="FULL_NAME"),
        LeadFormField(key="phone", label="Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="email", label="Business Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="company", label="Investment Entity / Fund Name"),
        LeadFormField(
            key="capital_ready", label="Available purchase capital?",
            field_type="SELECT",
            options=["Under $250k", "$250k - $500k", "$500k - $1M", "$1M - $5M", "$5M+"],
        ),
        LeadFormField(
            key="target_strategy", label="Primary investment strategy?",
            field_type="SELECT",
            options=["Fix & Flip", "Buy & Hold / Rental", "Commercial Repositioning", "Wholesale / Assignment"],
        ),
    ],
)

MED_SPA_CLINIC_FORM = LeadFormTemplate(
    name="Med Spa AI Patient Booking System",
    headline="Automate Patient Inquiries & Recover $25k+/mo in Lost Bookings",
    description="24/7 AI booking assistant that qualifies cosmetic procedure inquiries and collects consultation deposits.",
    thank_you_headline="Diagnostic Scheduled! ✨",
    thank_you_description="Our healthcare systems director will review your clinic profile.",
    vertical="med_spas",
    fields=[
        LeadFormField(key="full_name", label="Owner / Medical Director Name", prefill_from="FULL_NAME"),
        LeadFormField(key="phone", label="Direct Phone Number", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="email", label="Clinic Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="company", label="Practice / Clinic Name"),
        LeadFormField(
            key="treatment_types", label="Primary aesthetic services?",
            field_type="SELECT",
            options=["Injectables & Fillers", "Laser & Body Contouring", "Plastic Surgery", "Integrative & Wellness", "Multi-Specialty"],
        ),
    ],
)

CONTRACTOR_CONTECH_FORM = LeadFormTemplate(
    name="Commercial Contractor AI Estimating & Ops",
    headline="Automate Subcontractor Bids & Commercial Takeoffs in Minutes",
    description="AI-driven estimating and dispatch engine tailored for trade contractors and construction firms.",
    thank_you_headline="System Blueprint Ready! 🔨",
    thank_you_description="Our construction AI lead will reach out to demo automated takeoffs.",
    vertical="contractors_contech",
    fields=[
        LeadFormField(key="full_name", label="Owner / Principal Name", prefill_from="FULL_NAME"),
        LeadFormField(key="phone", label="Direct Phone", field_type="PHONE", prefill_from="PHONE"),
        LeadFormField(key="email", label="Work Email", field_type="EMAIL", prefill_from="EMAIL"),
        LeadFormField(key="company", label="Company Name"),
        LeadFormField(
            key="trade", label="Primary commercial trade?",
            field_type="SELECT",
            options=["HVAC & Mechanical", "Electrical & Controls", "Roofing & Siding", "General Contracting / Civil", "Plumbing"],
        ),
    ],
)

# Registry for easy iteration
ALL_TEMPLATES = {
    "ai_consultancy": AI_CONSULTANCY_FORM,
    "website_creation": WEBSITE_PROJECT_FORM,
    "app_development": APP_DEVELOPMENT_FORM,
    "real_estate_sellers": REAL_ESTATE_SELLER_FORM,
    "cash_buyers": CASH_BUYER_FORM,
    "med_spas": MED_SPA_CLINIC_FORM,
    "contractors_contech": CONTRACTOR_CONTECH_FORM,
}


def get_template(vertical: str) -> LeadFormTemplate:
    """Get a lead form template by vertical name."""
    return ALL_TEMPLATES.get(vertical, AI_CONSULTANCY_FORM)


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("  LEAD FORM TEMPLATES — Preview")
    print("=" * 60)
    for key, tmpl in ALL_TEMPLATES.items():
        print(f"\n{'─' * 50}")
        print(f"  📋 {tmpl.name}")
        print(f"  Headline: {tmpl.headline}")
        print(f"  Fields:   {len(tmpl.fields)}")
        print(f"  Vertical: {tmpl.vertical}")
        print(f"\n  Facebook Format:")
        fb = tmpl.to_facebook_format()
        print(f"    Questions: {len(fb['questions'])}")
        print(f"\n  Google Format:")
        ga = tmpl.to_google_format()
        print(f"    Fields: {len(ga['fields'])}")
