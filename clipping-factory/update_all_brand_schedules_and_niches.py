"""
Update All Brand Schedules & Niche Configurations
=================================================
Synchronizes all 5 brand folders in MBM-Social/Brands with exact user niches,
US prime-time schedules (20 posts/day per brand = 100 posts/day total),
and enhanced hashtag suites.

Run:
  python clipping-factory/update_all_brand_schedules_and_niches.py
"""

import os
import sys
import io
import json
import yaml
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
BRANDS_DIR = BASE_DIR / "MBM-Social" / "Brands"

BRAND_SPECS = {
    "twistsrevealed": {
        "display_name": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "gmail_account": "abdelshafyclapps@gmail.com",
        "niche": "Action & Thriller Movie Summaries & Insane Plot Twists",
        "primary_category": "Entertainment",
        "theme": "Action & Thriller movie summaries, insane plot twists, suspense recaps",
        "voice": "High-suspense narrative, dramatic shock-reveal",
        "keywords": ["plot twist", "action movie summary", "thriller recap", "cinema ending", "shocking reveal", "Hollywood twist"],
        "hashtags": ["#PlotTwist", "#MovieRecap", "#ActionMovies", "#Thriller", "#HollywoodEnding", "#USATrending", "#MovieClips", "#CinemaTok", "#MovieMindBlowing", "#Shorts", "#USA"],
        "posting_times_est": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00", "02:00", "03:00"],
        "target_region": "US",
        "default_language": "en-US"
    },
    "cutedosage": {
        "display_name": "Cute Dosage",
        "handle": "@CuteDosage",
        "gmail_account": "moeaiagenicteamz@gmail.com",
        "niche": "Cute Baby Videos, Adorable Moments, & Wholesome Family Clips",
        "primary_category": "Family & Pets",
        "theme": "Cute baby laughs, wholesome family moments, adorable baby clips",
        "voice": "Warm, uplifting, heartwarming, joyful",
        "keywords": ["cute baby", "baby laughing", "adorable baby", "wholesome moments", "heartwarming family"],
        "hashtags": ["#CuteBabies", "#BabyMoments", "#Wholesome", "#CuteBabiesOfTikTok", "#BabyLaugh", "#USAFamily", "#AdorableBabies", "#Heartwarming", "#Shorts", "#USA"],
        "posting_times_est": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00", "02:00", "03:00"],
        "target_region": "US",
        "default_language": "en-US"
    },
    "dontwatchthis": {
        "display_name": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "gmail_account": "abdelshafyplay@gmail.com",
        "niche": "Extremely Frightening Turkish Horror Movie Summaries & Massive Ocean Waves",
        "primary_category": "Horror & Mystery",
        "theme": "Terrifying Turkish horror recaps, dark atmosphere, colossal sea waves breaking",
        "voice": "Chilling, eerie, mysterious, high-retention horror",
        "keywords": ["Turkish horror", "scary movie summary", "ocean waves breaking", "frightening recaps", "spooky mystery"],
        "hashtags": ["#TurkishHorror", "#ScaryMovieRecap", "#OceanWaves", "#TerrifyingMoments", "#MegaWaves", "#HorrorTok", "#DontWatchThis", "#HauntedStories", "#Shorts", "#USA"],
        "posting_times_est": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00", "02:00", "03:00"],
        "target_region": "US",
        "default_language": "en-US"
    },
    "goalmachinez": {
        "display_name": "Goal Machinez",
        "handle": "@Goalmachinez",
        "gmail_account": "abdelshafyplays@gmail.com",
        "niche": "High-Energy Football & Physics-Defying Soccer Goals",
        "primary_category": "Sports",
        "theme": "Knuckleball free kicks, impossible football goals, high-energy soccer plays",
        "voice": "Energetic, hype, legendary sports commentary",
        "keywords": ["soccer goals", "knuckleball free kick", "football highlights", "physics defying goal", "Ronaldo free kick"],
        "hashtags": ["#Knuckleball", "#SoccerGoals", "#FootballHighlights", "#PhysicsDefying", "#GoalMachinez", "#RonaldoFreeKick", "#USASports", "#FutbolTok", "#Shorts", "#USA"],
        "posting_times_est": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00", "02:00", "03:00"],
        "target_region": "US",
        "default_language": "en-US"
    },
    "clippingfactorymbm": {
        "display_name": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "gmail_account": "UNKNOWN - NOT YET CONFIRMED",
        "niche": "AI Agent Swarms, Company Automation, & Video Clipping",
        "primary_category": "Technology & Business",
        "theme": "AI agent swarms, SaaS company automation, high-speed video clipping",
        "voice": "Futuristic, authoritative, high-efficiency tech",
        "keywords": ["AI agents", "automation", "SaaS automation", "video clipping", "build in public"],
        "hashtags": ["#AIAgents", "#Automation", "#SaaS", "#BuildInPublic", "#AIStartups", "#SiliconValley", "#VideoClipping", "#TechTok", "#USATech", "#Shorts", "#USA"],
        "posting_times_est": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00", "02:00", "03:00"],
        "target_region": "US",
        "default_language": "en-US"
    }
}


def sync_all_brand_configurations():
    print("==========================================================")
    print("  SYNCHRONIZING ALL BRAND NICHES & POSTING SCHEDULES      ")
    print("==========================================================")

    for slug, spec in BRAND_SPECS.items():
        b_dir = BRANDS_DIR / slug
        b_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n⚙️ Updating Brand Configs for [{slug.upper()}]...")

        # 1. brand.yaml
        brand_yaml_data = {
            "active": True,
            "slug": slug,
            "display_name": spec["display_name"],
            "handle": spec["handle"],
            "gmail_account": spec["gmail_account"],
            "master_account": "abdelshafyclapps@gmail.com",
            "primary_category": spec["primary_category"],
            "niche": spec["niche"],
            "theme": spec["theme"],
            "voice": spec["voice"],
            "keywords": spec["keywords"],
            "target_region": spec["target_region"],
            "default_language": spec["default_language"],
            "hashtags": spec["hashtags"],
            "neteller_wallet": "abdelshafyclapps@gmail.com (Account: 4599228811)"
        }
        (b_dir / "brand.yaml").write_text(yaml.dump(brand_yaml_data, sort_keys=False), encoding="utf-8")
        print(f"  [OK] Saved brand.yaml ({spec['niche']})")

        # 2. posting_schedule.yaml
        schedule_yaml_data = {
            "posts_per_day": 20,
            "target_audience": "US Only (en-US)",
            "time_zone": "America/New_York (EST)",
            "daily_post_times_est": spec["posting_times_est"],
            "platforms": ["YouTube Shorts", "Instagram Reels", "TikTok"],
            "interval_minutes": 72
        }
        (b_dir / "posting_schedule.yaml").write_text(yaml.dump(schedule_yaml_data, sort_keys=False), encoding="utf-8")
        print(f"  [OK] Saved posting_schedule.yaml (20 posts/day EST)")

        # 3. sources.yaml
        sources_yaml_data = {
            "niche": spec["niche"],
            "keywords": spec["keywords"],
            "preferred_aspect_ratio": "9:16",
            "target_fps": 60,
            "target_resolution": "1080x1920"
        }
        (b_dir / "sources.yaml").write_text(yaml.dump(sources_yaml_data, sort_keys=False), encoding="utf-8")
        print(f"  [OK] Saved sources.yaml")

        # 4. kpis.yaml
        kpis_yaml_data = {
            "daily_target_posts": 20,
            "monthly_target_views": 1000000,
            "target_conversion_rate": "2.5%",
            "primary_monetization": "Neteller Payout (4599228811)"
        }
        (b_dir / "kpis.yaml").write_text(yaml.dump(kpis_yaml_data, sort_keys=False), encoding="utf-8")
        print(f"  [OK] Saved kpis.yaml")

    print("\n==========================================================")
    print("✅ All 5 Brand Schedules & Niches Successfully Synchronized!")
    print("  - Total Posts Target: 100 Posts / Day (20 per brand)")
    print("  - Target Region: United States Only (en-US)")
    print("  - Monetization: Neteller Wallet 4599228811 (abdelshafyclapps@gmail.com)")
    print("==========================================================")


if __name__ == "__main__":
    sync_all_brand_configurations()
