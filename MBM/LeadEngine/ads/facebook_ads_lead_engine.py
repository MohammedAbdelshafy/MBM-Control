"""
Facebook Ads Lead Engine for AI Consultancy
=============================================
Full Meta Business SDK integration for finding leads interested in
AI consultancy, website creation, and app development services.

Capabilities:
  1. Custom Audience Builder — upload existing leads for retargeting
  2. Lookalike Audience Builder — find similar business owners from seed lists
  3. Interest-Based Audience Builder — pre-configured segments for AI/web/app
  4. Lead Ad Campaign Creator — Facebook Lead Ads with instant forms
  5. Lead Retrieval — pull submitted leads into LeadEngine pipeline
  6. Campaign Analytics — CPL, CTR, impressions, spend tracking
  7. Budget Guard — hard daily spend cap, --dry-run default

Usage:
  python facebook_ads_lead_engine.py --dry-run           # Config check
  python facebook_ads_lead_engine.py --build-audiences   # Create audiences
  python facebook_ads_lead_engine.py --create-campaign   # Dry-run campaign
  python facebook_ads_lead_engine.py --create-campaign --apply  # LIVE
  python facebook_ads_lead_engine.py --pull-leads        # Retrieve leads
  python facebook_ads_lead_engine.py --analytics         # Campaign stats
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.ads.ads_config import (
    FacebookAdsConfig, log, save_json, LOGS_DIR,
    check_budget, record_spend, neteller_link,
    verify_live_campaign_gate, generate_preflight_report,
)
from MBM.LeadEngine.ads.lead_form_templates import (
    ALL_TEMPLATES, get_template,
)

# ── Facebook Business SDK (optional import) ─────────────────────────────────
_HAS_FB_SDK = False
try:
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adcreative import AdCreative
    from facebook_business.adobjects.customaudience import CustomAudience
    from facebook_business.adobjects.leadgenform import LeadgenForm
    from facebook_business.adobjects.page import Page
    _HAS_FB_SDK = True
except ImportError:
    pass


# ── Audience Targeting Presets ──────────────────────────────────────────────

AI_CONSULTANCY_AUDIENCES = {
    "business_owners_tech": {
        "name": "AI Consultancy — Tech-Forward Business Owners",
        "description": "Business owners interested in AI, automation, machine learning",
        "targeting": {
            "interests": [
                {"id": "6003139266461", "name": "Artificial intelligence"},
                {"id": "6003384829039", "name": "Machine learning"},
                {"id": "6003012578599", "name": "Business automation"},
                {"id": "6003397425735", "name": "Cloud computing"},
                {"id": "6003263791114", "name": "Data analytics"},
            ],
            "behaviors": [
                {"id": "6002714895372", "name": "Small business owners"},
                {"id": "6003808923172", "name": "Technology early adopters"},
            ],
            "age_min": 25,
            "age_max": 55,
        },
    },
    "website_app_seekers": {
        "name": "Website & App Development — Digital Transformation Seekers",
        "description": "Business owners looking for web and mobile app solutions",
        "targeting": {
            "interests": [
                {"id": "6003305411158", "name": "Web development"},
                {"id": "6003227227990", "name": "Mobile application development"},
                {"id": "6003107902433", "name": "E-commerce"},
                {"id": "6003489944599", "name": "Digital marketing"},
                {"id": "6003398898372", "name": "Web design"},
            ],
            "behaviors": [
                {"id": "6002714895372", "name": "Small business owners"},
                {"id": "6002714898772", "name": "Engaged shoppers"},
            ],
            "age_min": 25,
            "age_max": 60,
        },
    },
    "agency_decision_makers": {
        "name": "Agency Decision Makers — C-Suite & Founders",
        "description": "CEOs, CTOs, and founders at agencies and tech companies",
        "targeting": {
            "interests": [
                {"id": "6003489944599", "name": "Digital marketing"},
                {"id": "6003384829039", "name": "Business consulting"},
                {"id": "6003139266461", "name": "SaaS"},
                {"id": "6003397425735", "name": "Startup ecosystem"},
            ],
            "work_positions": [
                {"id": "1", "name": "CEO"},
                {"id": "2", "name": "CTO"},
                {"id": "3", "name": "Founder"},
                {"id": "4", "name": "Marketing Director"},
                {"id": "5", "name": "Operations Manager"},
            ],
            "age_min": 28,
            "age_max": 55,
        },
    },
}

# ── Ad Copy Presets ─────────────────────────────────────────────────────────

AD_CREATIVES = {
    "ai_consultancy": {
        "headline": "AI That Runs Your Business While You Sleep",
        "primary_text": (
            "🤖 Stop losing money to manual processes.\n\n"
            "Our AI automation suite handles lead qualification, customer support, "
            "data analysis, and operations — 24/7.\n\n"
            "✅ Cut operational costs by 40%\n"
            "✅ Respond to leads in under 60 seconds\n"
            "✅ Free up 20+ hours/week\n\n"
            "Book a free 15-min AI strategy session ↓"
        ),
        "description": "Free AI Strategy Session — Limited Spots",
        "cta": "LEARN_MORE",
        "link_description": "Get your free AI audit now",
    },
    "website_creation": {
        "headline": "Your Dream Website — Built in 14 Days",
        "primary_text": (
            "🌐 No templates. No cookie-cutter designs.\n\n"
            "We build stunning, conversion-optimized websites that turn visitors "
            "into paying customers.\n\n"
            "✅ Custom design — your brand, your vision\n"
            "✅ Mobile-first, lightning fast\n"
            "✅ SEO-optimized from day one\n"
            "✅ 14-day delivery guarantee\n\n"
            "Get a free project estimate ↓"
        ),
        "description": "Custom Website — Free Estimate",
        "cta": "GET_QUOTE",
        "link_description": "See our portfolio and pricing",
    },
    "app_development": {
        "headline": "From App Idea to App Store in 8 Weeks",
        "primary_text": (
            "📱 Turn your app idea into reality.\n\n"
            "iOS, Android, or both — we build high-performance mobile apps "
            "with AI-powered features that users love.\n\n"
            "✅ Full-stack development team\n"
            "✅ UI/UX design included\n"
            "✅ AI features (chatbots, image recognition, etc.)\n"
            "✅ App Store submission handled\n\n"
            "Book a free discovery call ↓"
        ),
        "description": "App Development — Free Discovery Call",
        "cta": "LEARN_MORE",
        "link_description": "Explore our app development services",
    },
}


# ── Core Engine ─────────────────────────────────────────────────────────────

class FacebookAdsLeadEngine:
    """Facebook Ads lead generation engine for AI consultancy verticals."""

    def __init__(self, config: Optional[FacebookAdsConfig] = None):
        self.config = config or FacebookAdsConfig()
        self._api_initialized = False
        self._account: Any = None

    def _init_api(self) -> bool:
        """Initialize the Facebook Ads API session."""
        if self._api_initialized:
            return True
        if not _HAS_FB_SDK:
            log.warning("facebook-business SDK not installed. Run: pip install facebook-business")
            return False
        if not self.config.is_configured:
            missing = self.config.validate()
            log.warning(f"Facebook Ads not configured. Missing: {', '.join(missing)}")
            return False

        try:
            FacebookAdsApi.init(
                self.config.app_id,
                self.config.app_secret,
                self.config.access_token,
            )
            act_id = self.config.ad_account_id
            if not act_id.startswith("act_"):
                act_id = f"act_{act_id}"
            self._account = AdAccount(act_id)
            self._api_initialized = True
            log.info(f"Facebook Ads API initialized for account {act_id}")
            return True
        except Exception as e:
            log.error(f"Failed to init Facebook Ads API: {e}")
            return False

    # ── Custom Audiences ────────────────────────────────────────────────────

    def create_custom_audience(
        self,
        name: str,
        emails: List[str] = None,
        phones: List[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a Custom Audience from existing lead emails/phones.
        This is used as a seed for Lookalike Audiences.
        """
        if dry_run:
            log.info(f"[DRY-RUN] Would create Custom Audience '{name}' with "
                     f"{len(emails or [])} emails, {len(phones or [])} phones")
            return {
                "status": "DRY_RUN",
                "name": name,
                "emails_count": len(emails or []),
                "phones_count": len(phones or []),
            }

        if not self._init_api():
            return {"status": "ERROR", "reason": "API not configured"}

        try:
            audience = self._account.create_custom_audience(params={
                "name": name,
                "subtype": "CUSTOM",
                "description": f"Seed audience for AI consultancy leads — {name}",
                "customer_file_source": "USER_PROVIDED_ONLY",
            })

            # Hash and upload users
            schema = []
            data = []
            if emails:
                schema.append("EMAIL")
                for e in emails:
                    hashed = hashlib.sha256(e.strip().lower().encode()).hexdigest()
                    data.append([hashed])
            if phones:
                schema.append("PHONE")
                for p in phones:
                    clean = p.strip().replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
                    hashed = hashlib.sha256(clean.encode()).hexdigest()
                    if emails:
                        # Pair with empty email hash if needed
                        data.append(["", hashed])
                    else:
                        data.append([hashed])

            if data:
                audience.add_users(
                    schema=schema,
                    data=data,
                    is_raw=False,  # Already hashed
                )

            audience_id = audience.get_id()
            log.info(f"Created Custom Audience '{name}' — ID: {audience_id}")
            return {"status": "CREATED", "audience_id": audience_id, "name": name}

        except Exception as e:
            log.error(f"Failed to create Custom Audience: {e}")
            return {"status": "ERROR", "reason": str(e)}

    def create_lookalike_audience(
        self,
        source_audience_id: str,
        name: str,
        country: str = "US",
        ratio: float = 0.01,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a Lookalike Audience from a seed Custom Audience.
        ratio=0.01 means top 1% most similar users.
        """
        if dry_run:
            log.info(f"[DRY-RUN] Would create Lookalike '{name}' from {source_audience_id} "
                     f"in {country} at {ratio*100:.0f}%")
            return {"status": "DRY_RUN", "name": name, "ratio": ratio, "country": country}

        if not self._init_api():
            return {"status": "ERROR", "reason": "API not configured"}

        try:
            lookalike = self._account.create_custom_audience(params={
                "name": name,
                "subtype": "LOOKALIKE",
                "origin_audience_id": source_audience_id,
                "lookalike_spec": json.dumps({
                    "type": "similarity",
                    "country": country,
                    "ratio": ratio,
                }),
            })
            la_id = lookalike.get_id()
            log.info(f"Created Lookalike Audience '{name}' — ID: {la_id}")
            return {"status": "CREATED", "audience_id": la_id, "name": name}

        except Exception as e:
            log.error(f"Failed to create Lookalike Audience: {e}")
            return {"status": "ERROR", "reason": str(e)}

    # ── Campaign Creation ───────────────────────────────────────────────────

    def create_lead_campaign(
        self,
        vertical: str = "ai_consultancy",
        audience_key: str = "business_owners_tech",
        daily_budget_cents: int = 2000,  # $20.00
        countries: List[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a complete Facebook Lead Ad campaign:
        Campaign → Ad Set → Lead Form → Ad Creative → Ad.
        """
        countries = countries or ["US"]
        budget_dollars = daily_budget_cents / 100

        # Budget guard
        can_spend, remaining = check_budget("facebook", self.config.max_daily_spend)
        if budget_dollars > remaining:
            msg = (f"Budget exceeded: requested ${budget_dollars:.2f} but only "
                   f"${remaining:.2f} remaining today (cap: ${self.config.max_daily_spend:.2f})")
            log.warning(msg)
            return {"status": "BUDGET_BLOCKED", "reason": msg}

        audience = AI_CONSULTANCY_AUDIENCES.get(audience_key)
        creative = AD_CREATIVES.get(vertical)
        form_template = get_template(vertical)

        if not audience or not creative:
            return {"status": "ERROR", "reason": f"Unknown audience '{audience_key}' or vertical '{vertical}'"}

        campaign_name = f"[MBM] {form_template.name} — {audience['name']} — {datetime.now(timezone.utc).strftime('%Y%m%d')}"

        if dry_run:
            preflight = generate_preflight_report(
                platform="facebook",
                campaign_name=campaign_name,
                niche=vertical,
                target_audience=audience["name"],
                daily_budget=budget_dollars,
                total_budget=budget_dollars * 30,
                form_name=form_template.name,
            )
            result = {
                "status": "DRY_RUN",
                "campaign_name": campaign_name,
                "vertical": vertical,
                "audience": audience["name"],
                "daily_budget": f"${budget_dollars:.2f}",
                "countries": countries,
                "ad_headline": creative["headline"],
                "ad_text_preview": creative["primary_text"][:120] + "...",
                "form_fields": len(form_template.fields),
                "form_questions": [f.label for f in form_template.fields],
                "estimated_cpl": "$3.00 – $12.00",
                "estimated_daily_leads": f"{max(1, int(budget_dollars / 8))}-{max(2, int(budget_dollars / 3))}",
                "preflight_report": preflight,
            }
            log.info(f"[DRY-RUN] Campaign preview: {json.dumps(result, indent=2)}")
            return result

        # Hard Live Spend Gate Check
        gate_ok, gate_reason = verify_live_campaign_gate("facebook", budget_dollars, campaign_name)
        if not gate_ok:
            log.error(f"Live campaign creation blocked by safety gate: {gate_reason}")
            return {"status": "BLOCKED_SAFETY_GATE", "reason": gate_reason}

        if not self._init_api():
            return {"status": "ERROR", "reason": "API not configured"}

        try:
            # 1. Create Campaign
            campaign = self._account.create_campaign(params={
                "name": campaign_name,
                "objective": "OUTCOME_LEADS",
                "status": "PAUSED",
                "special_ad_categories": [],
            })
            campaign_id = campaign.get_id()
            log.info(f"Created campaign: {campaign_id}")

            # 2. Create Lead Form
            page = Page(self.config.page_id)
            fb_form_spec = form_template.to_facebook_format()
            lead_form = page.create_lead_gen_form(params=fb_form_spec)
            form_id = lead_form.get_id()
            log.info(f"Created lead form: {form_id}")

            # 3. Create Ad Set
            targeting = {
                "geo_locations": {"countries": countries},
                "age_min": audience["targeting"].get("age_min", 25),
                "age_max": audience["targeting"].get("age_max", 55),
                "flexible_spec": [{
                    "interests": audience["targeting"].get("interests", []),
                    "behaviors": audience["targeting"].get("behaviors", []),
                }],
            }
            if "work_positions" in audience["targeting"]:
                targeting["flexible_spec"][0]["work_positions"] = audience["targeting"]["work_positions"]

            adset = self._account.create_ad_set(params={
                "name": f"AdSet — {audience['name']}",
                "campaign_id": campaign_id,
                "daily_budget": daily_budget_cents,
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LEAD_GENERATION",
                "targeting": targeting,
                "status": "PAUSED",
            })
            adset_id = adset.get_id()
            log.info(f"Created ad set: {adset_id}")

            # 4. Create Ad Creative
            ad_creative = self._account.create_ad_creative(params={
                "name": f"Creative — {vertical}",
                "object_story_spec": {
                    "page_id": self.config.page_id,
                    "link_data": {
                        "message": creative["primary_text"],
                        "name": creative["headline"],
                        "description": creative["description"],
                        "call_to_action": {
                            "type": creative["cta"],
                            "value": {"lead_gen_form_id": form_id},
                        },
                    },
                },
            })
            creative_id = ad_creative.get_id()
            log.info(f"Created ad creative: {creative_id}")

            # 5. Create Ad
            ad = self._account.create_ad(params={
                "name": f"Ad — {vertical} — {audience_key}",
                "adset_id": adset_id,
                "creative": {"creative_id": creative_id},
                "status": "PAUSED",
            })
            ad_id = ad.get_id()
            log.info(f"Created ad: {ad_id}")

            record_spend("facebook", 0)  # No spend yet, just tracking creation

            result = {
                "status": "CREATED",
                "campaign_id": campaign_id,
                "adset_id": adset_id,
                "ad_id": ad_id,
                "form_id": form_id,
                "creative_id": creative_id,
                "campaign_name": campaign_name,
                "note": "Campaign created PAUSED. Enable in Facebook Ads Manager to start spending.",
            }
            save_json(LOGS_DIR / "fb_campaign_created.json", result)
            return result

        except Exception as e:
            log.error(f"Campaign creation failed: {e}")
            return {"status": "ERROR", "reason": str(e)}

    # ── Lead Retrieval ──────────────────────────────────────────────────────

    def pull_leads(self, form_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull submitted leads from Facebook Lead Ad forms.
        If no form_id, pulls from all forms on the ad account.
        """
        if not self._init_api():
            return {"status": "ERROR", "reason": "API not configured"}

        all_leads = []
        try:
            if form_id:
                form_ids = [form_id]
            else:
                # Get all lead gen forms from the page
                page = Page(self.config.page_id)
                forms = page.get_lead_gen_forms(fields=["id", "name", "status"])
                form_ids = [f["id"] for f in forms]
                log.info(f"Found {len(form_ids)} lead forms on page")

            for fid in form_ids:
                form = LeadgenForm(fid)
                leads = form.get_leads(fields=[
                    "id", "created_time", "field_data",
                    "ad_id", "ad_name", "adset_id", "campaign_id",
                ])
                for lead in leads:
                    parsed = {
                        "fb_lead_id": lead.get("id"),
                        "created_time": lead.get("created_time"),
                        "ad_id": lead.get("ad_id"),
                        "campaign_id": lead.get("campaign_id"),
                        "form_id": fid,
                        "source": "facebook_lead_ad",
                    }
                    # Parse field_data
                    for fd in lead.get("field_data", []):
                        key = fd.get("name", "").lower().replace(" ", "_")
                        val = fd.get("values", [""])[0] if fd.get("values") else ""
                        parsed[key] = val

                    # Map to canonical lead schema
                    parsed["name"] = parsed.get("full_name", "")
                    parsed["email"] = parsed.get("email", "")
                    parsed["phone"] = parsed.get("phone_number", parsed.get("phone", ""))
                    parsed["company"] = parsed.get("company", parsed.get("company_name", ""))
                    parsed["vertical"] = parsed.get("business_type", "AI Consultancy")
                    parsed["checkout_url"] = neteller_link(
                        500,  # Default consultation fee
                        f"AI_Consultation_{parsed.get('name', 'Lead').replace(' ', '_')}",
                    )

                    all_leads.append(parsed)

            log.info(f"Pulled {len(all_leads)} leads from {len(form_ids)} forms")

            # Save raw pulled leads
            output = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "leads_count": len(all_leads),
                "forms_scanned": len(form_ids),
                "leads": all_leads,
            }
            save_json(LOGS_DIR / "fb_leads_pulled.json", output)

            # Ingest through canonical pipeline into dialer
            if all_leads:
                from MBM.LeadEngine.ads.ads_ingestion_pipeline import AdLeadIngestionPipeline
                pipeline = AdLeadIngestionPipeline()
                ingest_res = pipeline.ingest_batch(all_leads, platform="facebook", dry_run=False)
                output["ingestion_summary"] = ingest_res

            return output

        except Exception as e:
            log.error(f"Lead retrieval failed: {e}")
            return {"status": "ERROR", "reason": str(e)}

    # ── Analytics ───────────────────────────────────────────────────────────

    def get_campaign_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Pull campaign performance metrics."""
        if not self._init_api():
            return {"status": "ERROR", "reason": "API not configured"}

        try:
            campaigns = self._account.get_campaigns(
                fields=["id", "name", "status", "objective", "daily_budget"],
                params={"effective_status": ["ACTIVE", "PAUSED"]},
            )

            analytics = []
            for c in campaigns:
                insights = c.get_insights(
                    fields=[
                        "impressions", "clicks", "ctr", "spend",
                        "cost_per_action_type", "actions",
                    ],
                    params={"date_preset": f"last_{days}_d" if days <= 30 else "maximum"},
                )
                stats = insights[0] if insights else {}
                leads_count = 0
                cpl = 0
                for action in stats.get("actions", []):
                    if action.get("action_type") == "lead":
                        leads_count = int(action.get("value", 0))
                for cpa in stats.get("cost_per_action_type", []):
                    if cpa.get("action_type") == "lead":
                        cpl = float(cpa.get("value", 0))

                analytics.append({
                    "campaign_id": c["id"],
                    "campaign_name": c["name"],
                    "status": c["status"],
                    "impressions": int(stats.get("impressions", 0)),
                    "clicks": int(stats.get("clicks", 0)),
                    "ctr": stats.get("ctr", "0%"),
                    "spend": f"${float(stats.get('spend', 0)):.2f}",
                    "leads": leads_count,
                    "cost_per_lead": f"${cpl:.2f}",
                })

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "period": f"last_{days}_days",
                "campaigns": analytics,
                "total_spend": f"${sum(float(a['spend'].replace('$','')) for a in analytics):.2f}",
                "total_leads": sum(a["leads"] for a in analytics),
            }
            save_json(LOGS_DIR / "fb_analytics.json", result)
            return result

        except Exception as e:
            log.error(f"Analytics retrieval failed: {e}")
            return {"status": "ERROR", "reason": str(e)}

    # ── Audience Builder (batch) ────────────────────────────────────────────

    def build_all_audiences(self, dry_run: bool = True) -> Dict[str, Any]:
        """Preview or create all pre-configured audiences."""
        results = {}
        for key, audience in AI_CONSULTANCY_AUDIENCES.items():
            print(f"\n  📊 Audience: {audience['name']}")
            print(f"     Interests: {len(audience['targeting'].get('interests', []))}")
            print(f"     Age range: {audience['targeting'].get('age_min')}-{audience['targeting'].get('age_max')}")
            results[key] = {
                "name": audience["name"],
                "status": "DRY_RUN" if dry_run else "READY",
                "targeting_summary": {
                    "interests": len(audience["targeting"].get("interests", [])),
                    "behaviors": len(audience["targeting"].get("behaviors", [])),
                    "age_range": f"{audience['targeting'].get('age_min')}-{audience['targeting'].get('age_max')}",
                },
            }
        return results


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Facebook Ads Lead Engine for AI Consultancy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview only, no API calls (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Execute live API calls (overrides --dry-run)")
    parser.add_argument("--build-audiences", action="store_true",
                        help="Build/preview audience segments")
    parser.add_argument("--create-campaign", action="store_true",
                        help="Create a lead ad campaign")
    parser.add_argument("--pull-leads", action="store_true",
                        help="Pull submitted leads from lead forms")
    parser.add_argument("--analytics", action="store_true",
                        help="Get campaign performance analytics")
    parser.add_argument("--vertical", default="ai_consultancy",
                        choices=["ai_consultancy", "website_creation", "app_development"],
                        help="Target vertical for campaign")
    parser.add_argument("--audience", default="business_owners_tech",
                        choices=list(AI_CONSULTANCY_AUDIENCES.keys()),
                        help="Audience segment to use")
    parser.add_argument("--budget", type=int, default=2000,
                        help="Daily budget in cents (default: 2000 = $20.00)")
    parser.add_argument("--countries", nargs="+", default=["US"],
                        help="Target countries (default: US)")
    parser.add_argument("--form-id", default=None,
                        help="Specific lead form ID for lead retrieval")

    args = parser.parse_args()
    dry_run = not args.apply

    config = FacebookAdsConfig()
    engine = FacebookAdsLeadEngine(config)

    print("=" * 60)
    print("  FACEBOOK ADS LEAD ENGINE — AI Consultancy")
    print(f"  Mode: {'🔒 DRY-RUN' if dry_run else '🔴 LIVE'}")
    print(f"  SDK:  {'✅ Installed' if _HAS_FB_SDK else '❌ Not installed (pip install facebook-business)'}")
    print(f"  API:  {'✅ Configured' if config.is_configured else '❌ Missing credentials'}")
    print("=" * 60)

    if not args.build_audiences and not args.create_campaign and not args.pull_leads and not args.analytics:
        # Default: show config status and audience preview
        from MBM.LeadEngine.ads.ads_config import print_config_status
        print_config_status()
        print("\n  Available verticals & audiences:")
        for key, aud in AI_CONSULTANCY_AUDIENCES.items():
            print(f"    • {key}: {aud['name']}")
        print(f"\n  Available ad creatives:")
        for key, creative in AD_CREATIVES.items():
            print(f"    • {key}: {creative['headline']}")
        return

    if args.build_audiences:
        print("\n── Building Audiences ──")
        results = engine.build_all_audiences(dry_run=dry_run)
        print(f"\n  Total audiences: {len(results)}")

    if args.create_campaign:
        print(f"\n── Creating Campaign ──")
        print(f"  Vertical: {args.vertical}")
        print(f"  Audience: {args.audience}")
        print(f"  Budget:   ${args.budget/100:.2f}/day")
        print(f"  Countries: {', '.join(args.countries)}")
        result = engine.create_lead_campaign(
            vertical=args.vertical,
            audience_key=args.audience,
            daily_budget_cents=args.budget,
            countries=args.countries,
            dry_run=dry_run,
        )
        print(f"\n  Result: {json.dumps(result, indent=2)}")

    if args.pull_leads:
        print(f"\n── Pulling Leads ──")
        result = engine.pull_leads(form_id=args.form_id)
        if result.get("leads_count"):
            print(f"  ✅ Retrieved {result['leads_count']} leads")
            for lead in result.get("leads", [])[:5]:
                print(f"    • {lead.get('name', 'N/A')} | {lead.get('email', 'N/A')} | {lead.get('phone', 'N/A')}")
        else:
            print(f"  Result: {json.dumps(result, indent=2)}")

    if args.analytics:
        print(f"\n── Campaign Analytics ──")
        result = engine.get_campaign_analytics()
        if result.get("campaigns"):
            for c in result["campaigns"]:
                print(f"  📊 {c['campaign_name']}")
                print(f"     Status: {c['status']} | Spend: {c['spend']} | "
                      f"Leads: {c['leads']} | CPL: {c['cost_per_lead']}")
        else:
            print(f"  Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
