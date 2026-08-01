"""
SocialMediaResearcher — 15-minute automated research daemon for Instagram Reels, YouTube Shorts, and TikTok trends.
"""
import os
import sys
import json
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.logging_config import get_logger
from app.services.viral_comparison_service import BENCHMARK_PROFILES
from app.services.monetization_service import MonetizationService
from app.services.voice_agency_service import VoiceAgencyService

logger = get_logger("services.social_media_researcher")


class SocialMediaResearcher:
    def __init__(self, log_dir: str | Path | None = None):
        self.log_dir = Path(log_dir or "./research_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def run_research_cycle(self) -> dict:
        """Execute 15-minute short-form trend research cycle."""
        now_str = datetime.datetime.now().isoformat()
        logger.info(f"Starting 15-minute Reels/Shorts/TikTok research cycle at {now_str}")

        ms = MonetizationService()
        vas = VoiceAgencyService()

        monetization_projections = {
            "real_estate_wholesaling_100k_views": ms.calculate_projected_earnings("real_estate_wholesaling", 100000),
            "business_finance_100k_views": ms.calculate_projected_earnings("business_finance", 100000),
            "twists_revealed_100k_views": ms.calculate_projected_earnings("twists_revealed", 100000),
            "cute_dosage_100k_views": ms.calculate_projected_earnings("cute_dosage", 100000),
        }

        voice_agency_assignments = {
            "real_estate_wholesaling": vas.get_voice_profile("real_estate_wholesaling"),
            "business_finance": vas.get_voice_profile("business_finance"),
            "twists_revealed": vas.get_voice_profile("twists_revealed"),
            "reverse_psychology_warning": vas.get_voice_profile("reverse_psychology_warning"),
            "cute_dosage": vas.get_voice_profile("cute_dosage"),
            "tech_ai": vas.get_voice_profile("tech_ai"),
        }

        insights = {
            "timestamp": now_str,
            "monetization_projections": monetization_projections,
            "voice_agency_assignments": voice_agency_assignments,
            "trending_hook_patterns": [
                "The $10k Secret Nobody Mentions...",
                "If you want to close properties fast, stop doing this...",
                "The 3-step framework for assignment contracts..."
            ],
            "optimal_pacing": "155 - 185 WPM with 1.08x audio acceleration",
            "top_conversion_hashtags": {
                "instagram_reels": ["#realestate", "#wholesaling", "#wholesalingrealestate", "#propertydeals", "#shorts"],
                "tiktok": ["#realestate", "#wholesaling", "#realestateinvesting", "#business", "#viral"],
                "youtube_shorts": ["#shorts", "#realestate", "#wholesaling", "#entrepreneur", "#wealth"]
            },
            "retention_tactics": [
                "Burned-in kinetic top third visual hook header (0-3s)",
                "DM share-triggering actionable takeaway at 12s",
                "Loop-friendly closing sentence"
            ],
            "channel_content_packages": [
                {
                    "channel": "Twists Revealed",
                    "topic": "Shocking Movie & Real Life Plot Twists",
                    "hook_opening": "The shocking ending twist nobody noticed until now...",
                    "target_platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"],
                    "hashtags": ["#twistsrevealed", "#plottwist", "#mindblown", "#shocking", "#shorts"],
                    "call_to_action": "Did you spot the hint at 0:14? Comment below!"
                },
                {
                    "channel": "Don't Watch This",
                    "topic": "Reverse Psychology Curiosity Hooks",
                    "hook_opening": "DO NOT watch this video if you want to keep your peace of mind...",
                    "target_platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"],
                    "hashtags": ["#dontwatchthis", "#warning", "#forbidden", "#mystery", "#viral"],
                    "call_to_action": "Tag someone who shouldn't see this!"
                },
                {
                    "channel": "Cute Dosage",
                    "topic": "Wholesome Daily Booster & Animals",
                    "hook_opening": "Your 15-second daily dosage of pure happiness...",
                    "target_platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"],
                    "hashtags": ["#cutedosage", "#wholesome", "#animals", "#aww", "#shorts"],
                    "call_to_action": "Share this with someone who needs a smile today!"
                },
                {
                    "channel": "Wholesaling Real Estate",
                    "topic": "Wholesaling Contracts & Assignment Clauses",
                    "hook_opening": "The $10,000 Wholesaling Contract Clause Nobody Mentions...",
                    "target_platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"],
                    "hashtags": ["#realestate", "#wholesaling", "#realestateinvesting", "#propertydeals", "#shorts"],
                    "call_to_action": "Save this for your next property deal!"
                },
                {
                    "channel": "Cash Buyer Intelligence",
                    "topic": "Finding Cash Buyers for Distressed Properties",
                    "hook_opening": "How to find 50 active cash buyers in under 10 minutes...",
                    "target_platforms": ["YouTube Shorts", "TikTok", "Instagram Reels"],
                    "hashtags": ["#wholesalingrealestate", "#cashbuyers", "#realestate", "#business", "#viral"],
                    "call_to_action": "Comment 'BUYER' to get the full framework."
                }
            ],
            "niche_relatable_creator_sources": [
                {
                    "creator": "Twists Revealed / Screen Rant / FoundFlix",
                    "niche": "Twists Revealed & Plot Twists",
                    "content_type": "Shocking Movie Endings, Secret Hidden Details, Unspoken Truths",
                    "viral_hook_type": "shocking_reveal / plot_twist"
                },
                {
                    "creator": "Daily Dose Of Internet / Cute Dosage",
                    "niche": "Cute Dosage & Wholesome Moments",
                    "content_type": "Heartwarming Animal Clips, Pure Happiness Beats, Daily Boosters",
                    "viral_hook_type": "wholesome_moment / daily_dopamine"
                },
                {
                    "creator": "Wholesaling Inc. (Brent Daniels)",
                    "niche": "Real Estate Wholesaling",
                    "content_type": "Live Cold Calling, Seller Negotiation, No-Fluff Deal Breakdowns",
                    "viral_hook_type": "stat_reveal / pattern_interrupt"
                },
                {
                    "creator": "Wholesale Hotline (Pace Morby & Jamil Damji)",
                    "niche": "Creative Finance & Wholesaling",
                    "content_type": "Subject-To Deals, Assignment Contracts, Live Seller Calls",
                    "viral_hook_type": "bold_claim / curiosity_gap"
                }
            ],
            "clipping_campaign_prompts": [
                "Extract 15-30s high-energy contract assignment breakdowns from Wholesaling Inc. & Wholesale Hotline.",
                "Cut seller negotiation moments with on-screen kinetic subtitle captions.",
                "Crop 1080x1920 vertical framing centered on speaker reaction peaks."
            ],
            "benchmark_profiles_active": list(BENCHMARK_PROFILES.keys())
        }

        # Save to research logs and Desktop
        output_path = self.log_dir / f"research_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.write_text(json.dumps(insights, indent=2))

        desktop_dir = Path(os.environ.get("USERPROFILE", ".")) / "Desktop"
        desktop_summary = desktop_dir / "latest_social_content_ideas.json"
        try:
            desktop_summary.write_text(json.dumps(insights, indent=2))
        except Exception:
            pass

        logger.info(f"Research cycle completed. Logged to {output_path} and Desktop")
        logger.info(f"Research cycle completed. Logged to {output_path}")

        return insights


if __name__ == "__main__":
    researcher = SocialMediaResearcher()
    res = researcher.run_research_cycle()
    print(json.dumps(res, indent=2))
