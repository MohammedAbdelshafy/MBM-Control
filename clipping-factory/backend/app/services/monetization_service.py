"""
MonetizationService — Calculates RPM revenue projections, channel monetization tiers,
affiliate CTA strategies, and automated payout estimations across multi-platform clipping campaigns.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.logging_config import get_logger

logger = get_logger("services.monetization")

# RPM (Revenue per 1,000 views) estimates by niche & platform
RPM_BENCHMARKS = {
    "real_estate_wholesaling": {
        "youtube_shorts": 18.50, # High CPM real estate lead gen
        "tiktok": 12.00,
        "instagram_reels": 22.00, # DM automation / lead capture
        "x_twitter": 15.00,
        "monetization_models": [
            "Assignment Contract Lead Capture ($500-$2,000 per deal referral)",
            "High-Ticket Cash Buyer List Subscriptions",
            "Wholesaling Masterclass Affiliate Links"
        ]
    },
    "business_finance": {
        "youtube_shorts": 12.00,
        "tiktok": 8.50,
        "instagram_reels": 14.00,
        "x_twitter": 10.00,
        "monetization_models": [
            "SaaS & AI Tool Affiliate Commissions",
            "Financial Brokerage / Trading Referrals",
            "Sponsorship Banners & Pinned Comments"
        ]
    },
    "twists_revealed": {
        "youtube_shorts": 3.50,
        "tiktok": 2.80,
        "instagram_reels": 3.20,
        "x_twitter": 2.50,
        "monetization_models": [
            "High Volume AdSense Revenue Share",
            "TikTok Creator Rewards Program (>60s clips)",
            "Movie / Media Affiliate Promotions"
        ]
    },
    "reverse_psychology_warning": {
        "youtube_shorts": 4.00,
        "tiktok": 3.20,
        "instagram_reels": 4.50,
        "x_twitter": 3.00,
        "monetization_models": [
            "High Retention Ad Monetization",
            "Mystery Niche Affiliate Offers",
            "Newsletter / Email List Opt-Ins"
        ]
    },
    "cute_dosage": {
        "youtube_shorts": 2.50,
        "tiktok": 2.20,
        "instagram_reels": 2.80,
        "x_twitter": 1.80,
        "monetization_models": [
            "Mass View Creator Fund / Ad Share",
            "Pet Product E-Commerce Affiliate Links",
            "Merchandise Store Conversions"
        ]
    }
}


class MonetizationService:
    def __init__(self):
        self.logger = logger

    def calculate_projected_earnings(self, niche: str, views: int) -> dict:
        """Calculate projected earnings across platforms for a given view volume."""
        profile = RPM_BENCHMARKS.get(niche, RPM_BENCHMARKS["business_finance"])
        thousands = views / 1000.0

        yt_earnings = round(thousands * profile["youtube_shorts"], 2)
        tt_earnings = round(thousands * profile["tiktok"], 2)
        ig_earnings = round(thousands * profile["instagram_reels"], 2)
        x_earnings = round(thousands * profile["x_twitter"], 2)
        total = round(yt_earnings + tt_earnings + ig_earnings + x_earnings, 2)

        return {
            "niche": niche,
            "total_views": views,
            "projected_total_earnings_usd": total,
            "platform_breakdown": {
                "youtube_shorts": {"rpm": profile["youtube_shorts"], "projected_usd": yt_earnings},
                "tiktok": {"rpm": profile["tiktok"], "projected_usd": tt_earnings},
                "instagram_reels": {"rpm": profile["instagram_reels"], "projected_usd": ig_earnings},
                "x_twitter": {"rpm": profile["x_twitter"], "projected_usd": x_earnings},
            },
            "monetization_strategies": profile["monetization_models"],
        }

    def generate_monetized_cta(self, channel_name: str, niche: str) -> dict:
        """Generate high-converting monetized Call-To-Action (CTA) for captions & pinned comments."""
        if "wholesaling" in niche.lower() or "real estate" in channel_name.lower():
            cta = {
                "pinned_comment": "💰 Want my $10,000 Wholesaling Contract Template & Cash Buyer Script for FREE? Tap link in bio or DM 'CONTRACT'! 👇",
                "caption_cta": "📲 DM 'DEAL' to get added to our VIP Off-Market Cash Buyers List!",
                "affiliate_link_slot": "https://clippingfactory.ai/wholesaling-contract-template"
            }
        elif "twist" in niche.lower() or "warning" in niche.lower():
            cta = {
                "pinned_comment": "🔍 Subscribe & turn on notifications so you never miss a mind-blowing reveal! What was your reaction? 👇",
                "caption_cta": "👀 Share this with a friend who needs to see the ending twist!",
                "affiliate_link_slot": "https://clippingfactory.ai/viral-reveals"
            }
        elif "cute" in niche.lower():
            cta = {
                "pinned_comment": "🐾 Share this daily dose of cute to make someone's day brighter! 💖 Subscribe for daily happiness!",
                "caption_cta": "🐶 Double tap if this made you smile today!",
                "affiliate_link_slot": "https://clippingfactory.ai/cute-dosage-merch"
            }
        else:
            cta = {
                "pinned_comment": "🚀 Want to automate your business & growth? Get our top tools guide in bio link! 👇",
                "caption_cta": "💡 Save this post & follow for daily business insights!",
                "affiliate_link_slot": "https://clippingfactory.ai/growth-tools"
            }

        cta["youtube_shorts_tactics"] = {
            "viewed_vs_swiped_target": "> 70% Viewed Ratio",
            "related_video_link": cta["affiliate_link_slot"],
            "infinite_loop_audio": "Seamless 2x re-watch sentence end",
            "ypp_shorts_threshold": "10,000,000 Shorts Views in 90 Days"
        }
        cta["instagram_trial_reels_tactics"] = {
            "mode": "Trial Reel (Cold Non-Follower Audience Only)",
            "test_duration": "24-48 Hours",
            "auto_grid_publish_trigger": "Completion Rate > 75% AND DM Share Rate > 5%",
            "variant_strategy": "A/B test 3 hook headers risk-free"
        }
        return cta


if __name__ == "__main__":
    ms = MonetizationService()
    res = ms.calculate_projected_earnings("real_estate_wholesaling", 100000)
    print(json.dumps(res, indent=2))
