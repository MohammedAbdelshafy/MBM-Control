"""
Test script for ViralComparisonService & ViralBenchmarkAgent
"""
import sys
import io
from pathlib import Path

# Fix Windows stdout encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add app directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.viral_comparison_service import ViralComparisonService

def test_viral_comparison_service():
    print("Initializing ViralComparisonService test...")
    service = ViralComparisonService()

    sample_transcript = (
        "Did you know that 90 percent of people fail at building habits because they start too big? "
        "Here is the exact 3-step framework to master any skill in 30 days without burning out. "
        "Step 1: Start with just 2 minutes every morning. Step 2: Track your streak visually. "
        "Step 3: Never miss twice in a row. Comment 'HABIT' below and I will send you the full breakdown!"
    )
    sample_hook = "Did you know that 90% of people fail at building habits because they start too big?"
    sample_tags = ["#productivity", "#mindset", "habits"]

    # Test 1: Compare to Business / Finance / Productivity Viral Benchmark
    report = service.compare_clip_to_viral(
        transcript_text=sample_transcript,
        hook_text=sample_hook,
        current_tags=sample_tags,
        duration_seconds=35.0,
        niche="business_finance"
    )

    print("\n--- COMPARISON REPORT ---")
    print(f"Niche: {report['niche']}")
    print(f"Overall Viral Score: {report['overall_viral_score']}% ({report['tier']})")
    print(f"Metrics Breakdown: {report['metrics']}")
    print(f"Hook Type Detected: {report['hook_analysis']['detected_type']}")
    print(f"Gap Analysis: {report['gap_analysis']}")

    # Test 2: Generate Enhancements
    enhancements = service.generate_viral_enhancements(
        transcript_text=sample_transcript,
        hook_text=sample_hook,
        current_tags=sample_tags,
        niche="business_finance"
    )

    print("\n--- VIRAL ENHANCEMENTS ---")
    print(f"Enhanced Viral Hooks: {enhancements['enhanced_viral_hooks']}")
    print(f"Enhanced Tags: {enhancements['enhanced_tags']}")
    print(f"Hashtags String: {enhancements['hashtags_string']}")
    print(f"YouTube Shorts Title: {enhancements['platform_metadata']['youtube_shorts']['title']}")
    print(f"TikTok Caption: {enhancements['platform_metadata']['tiktok']['caption']}")

    assert report["overall_viral_score"] > 0, "Overall score should be > 0"
    assert len(enhancements["enhanced_tags"]) >= 5, "Enhanced tags count should be >= 5"
    print("\n✅ VIRAL COMPARISON SERVICE TEST PASSED CLEANLY!")

if __name__ == "__main__":
    test_viral_comparison_service()
