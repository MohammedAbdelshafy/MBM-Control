"""
Upload all demo videos to YouTube Shorts via Data API.
Requires: youtube_tokens.json with at least one channel configured.

Usage:
  cd clipping-factory/backend
  .venv\Scripts\python.exe scripts\upload_demos_youtube.py
  .venv\Scripts\python.exe scripts\upload_demos_youtube.py --channel CHANNEL_ID
  .venv\Scripts\python.exe scripts\upload_demos_youtube.py --privacy unlisted
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DEMOS_DIR = Path(__file__).parent.parent.parent.parent / "public" / "demos"

DEMOS = [
    {
        "file": "demo_intro.mp4",
        "title": "Contech AI Agentic teamz — AI-Powered Waste Collection",
        "description": "Meet Contech AI Agentic teamz — the AI platform that automates waste collection operations, route optimization, and commission tracking.\n\nFirst week free for all new users.\n\n#AI #WasteManagement #SmartCity #Automation #TechDemo",
        "tags": ["AI", "waste management", "smart city", "automation", "tech demo", "Contech"],
    },
    {
        "file": "demo_dealing-room.mp4",
        "title": "Dealing Room — Real-Time Deal Pipeline",
        "description": "See how the Dealing Room tracks your real estate deals in real-time with AI-powered insights.\n\nFirst week free.\n\n#RealEstate #DealPipeline #Proptech #AI",
        "tags": ["real estate", "deal pipeline", "proptech", "AI", "dealing room"],
    },
    {
        "file": "demo_subscriptions.mp4",
        "title": "Subscription Management — Automated Billing",
        "description": "Automated billing, renewals, and subscription analytics — all in one dashboard.\n\nFirst week free.\n\n#SaaS #Subscription #Billing #Automation",
        "tags": ["SaaS", "subscription", "billing", "automation", "fintech"],
    },
    {
        "file": "demo_route-optimization.mp4",
        "title": "Smart Route Optimization — AI Route Planning",
        "description": "AI-powered route optimization cuts fuel costs and collection time by 40%.\n\nFirst week free.\n\n#Logistics #RouteOptimization #AI #FleetManagement",
        "tags": ["logistics", "route optimization", "AI", "fleet management", "smart routes"],
    },
    {
        "file": "demo_commissions.mp4",
        "title": "Commission Tracking — Automated Calculations",
        "description": "Never miss a commission payment. Automated tracking and real-time reporting.\n\nFirst week free.\n\n#Sales #Commission #Automation #Fintech",
        "tags": ["sales", "commission", "automation", "fintech", "tracking"],
    },
    {
        "file": "demo_kpi-dashboard.mp4",
        "title": "KPI Dashboard — Real-Time Business Intelligence",
        "description": "Monitor every metric that matters with AI-powered dashboards and alerts.\n\nFirst week free.\n\n#Analytics #KPI #Dashboard #BusinessIntelligence",
        "tags": ["analytics", "KPI", "dashboard", "business intelligence", "real-time"],
    },
    {
        "file": "demo_ai-clipping.mp4",
        "title": "AI Clipping Engine — Autonomous Video Production",
        "description": "AI automatically clips, edits, and publishes video content across all platforms.\n\nFirst week free.\n\n#AI #VideoEditing #ContentCreation #Automation",
        "tags": ["AI", "video editing", "content creation", "automation", "clipping"],
    },
    {
        "file": "demo_outro.mp4",
        "title": "Get Started Today — First Week Free",
        "description": "Join Contech AI Agentic teamz today. First week free for all new users.\n\n#TryFree #AI #WasteManagement #TechStartup",
        "tags": ["try free", "AI", "waste management", "tech startup", "Contech"],
    },
]


def main():
    parser = argparse.ArgumentParser(description="Upload demo videos to YouTube Shorts")
    parser.add_argument("--channel", default=None, help="Channel ID (default: first configured)")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--list-channels", action="store_true", help="List configured channels")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if video already uploaded")
    args = parser.parse_args()

    from app.services.youtube_upload import YouTubeUploader

    uploader = YouTubeUploader()

    if args.list_channels:
        channels = uploader.list_channels()
        if not channels:
            print("No channels configured. Run youtube_oauth_setup.py first.")
        else:
            print("Configured channels:")
            for ch in channels:
                print(f"  {ch['channel_name']}: {ch['channel_id']}")
        return

    print("=" * 60)
    print("YouTube Shorts — Demo Upload")
    print("=" * 60)
    print(f"Privacy: {args.privacy}")
    print(f"Channel: {args.channel or 'default'}")
    print()

    results = []
    for demo in DEMOS:
        video_path = DEMOS_DIR / demo["file"]
        if not video_path.exists():
            print(f"SKIP: {demo['file']} not found")
            results.append({"file": demo["file"], "status": "skipped"})
            continue

        print(f"Uploading: {demo['file']}")
        try:
            result = uploader.upload_short(
                video_path=str(video_path),
                title=demo["title"],
                description=demo["description"],
                tags=demo["tags"],
                channel_id=args.channel,
            )
            # Override privacy if not default
            if args.privacy != "public":
                result["privacy"] = args.privacy
            print(f"  OK: {result['url']}")
            results.append({"file": demo["file"], "status": "uploaded", "url": result["url"]})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"file": demo["file"], "status": "error", "error": str(e)})

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    uploaded = sum(1 for r in results if r["status"] == "uploaded")
    errors = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"  Uploaded: {uploaded}/{len(DEMOS)}")
    print(f"  Errors:   {errors}")
    print(f"  Skipped:  {skipped}")
    for r in results:
        status = "✓" if r["status"] == "uploaded" else "✗" if r["status"] == "error" else "—"
        url = r.get("url", "")
        print(f"  {status} {r['file']} {url}")


if __name__ == "__main__":
    main()
