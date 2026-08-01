"""
Full End-to-End Pipeline Execution Script
Ingests a real YouTube streaming video, cuts clips, applies viral comparisons & enhanced tags,
runs Quality Control, and publishes across social platforms.
"""
import os
import sys
import io
import json
import traceback
from pathlib import Path

# Fix Windows stdout encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add backend directory to sys.path
BACKEND = Path(__file__).parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

if "DATABASE_URL" not in os.environ or "postgresql" in os.environ.get("DATABASE_URL", ""):
    os.environ["DATABASE_URL"] = "sqlite:///./clipping_factory.db"


def log_header(title: str):
    print(f"\n{'='*70}\n🚀 {title}\n{'='*70}", flush=True)


def safe_commit(db, retries=5, delay=1.0):
    for i in range(retries):
        try:
            db.commit()
            return
        except Exception:
            db.rollback()
            if i == retries - 1:
                raise
            time.sleep(delay * (i + 1))


def main():
    from app.core.database import SyncSessionLocal, sync_engine, Base
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.clip import Clip
    from app.models.source_content import SourceContent
    from app.agents.content_acquisition import ContentAcquisitionAgent
    from app.agents.content_analysis import ContentAnalysisAgent
    from app.agents.clip_generation import ClipGenerationAgent
    from app.agents.editing_agent import EditingAgent
    from app.agents.viral_benchmark_agent import ViralBenchmarkAgent
    from app.agents.quality_control import QualityControlAgent
    from app.agents.publishing import PublishingAgent

    # Ensure all tables exist on the database
    try:
        with sync_engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
    except Exception:
        pass

    Base.metadata.create_all(sync_engine)
    db = SyncSessionLocal()

    # Target Video URL to process (YouTube, Instagram Reel, TikTok, or Direct URL)
    video_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    if video_url == "default":
        video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

    log_header(f"STARTING FULL PIPELINE: Stream Source = {video_url}")

    # 1. Create or retrieve Campaign for this YouTube URL
    campaign = (
        db.query(Campaign)
        .filter(Campaign.source_url == video_url)
        .order_by(Campaign.created_at.desc())
        .first()
    )

    from app.models.page import Page
    page = db.query(Page).first()
    if not page:
        import uuid
        page = Page(
            name="Viral Clipping Creator",
            platform_id=f"page_{uuid.uuid4().hex[:8]}",
            email="creator@clippingfactory.ai",
            is_active=True
        )
        db.add(page)
        db.commit()
        db.refresh(page)

    if not campaign:
        import uuid
        platform_name = "Instagram" if "instagram.com" in video_url else ("TikTok" if "tiktok.com" in video_url else "YouTube")
        campaign = Campaign(
            page_id=page.id,
            platform_campaign_id=f"clip_{uuid.uuid4().hex[:8]}",
            title=f"Viral Stream Campaign - {video_url[-15:]}",
            brand_name="Viral Shorts & Reels",
            source_url=video_url,
            platform_name=platform_name,
            status=CampaignStatus.DISCOVERED,
            opportunity_score=0.92,
            requirements={
                "duration_min": 15,
                "duration_max": 45,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "platform": "TikTok",
                "caption_required": True,
                "hook_required": True,
                "niche": "business_finance",
                "remove_silence": True,
            }
        )
def safe_commit(db, retries=5, delay=1.0):
    for i in range(retries):
        try:
            db.commit()
            return
        except Exception:
            db.rollback()
            if i == retries - 1:
                raise
            time.sleep(delay * (i + 1))

    print(f"[*] Campaign Loaded: ID={campaign.id}, Title='{campaign.title}'")

    # ---- Stage 1: Content Acquisition (Download from YouTube via yt-dlp) ----
    log_header("STAGE 1/6: CONTENT ACQUISITION (YouTube Stream Download)")
    acq_agent = ContentAcquisitionAgent(db)
    r1 = acq_agent._safe_run(campaign_id=campaign.id)
    db.commit()
    if not r1.success:
        print(f"❌ ACQUISITION FAILED: {r1.error}")
        return 1

    source_content_id = r1.data["source_content_id"]
    source = db.query(SourceContent).filter(SourceContent.id == source_content_id).first()
    print(f"✅ Downloaded YouTube Video Successfully!")
    print(f"   - Source ID: {source_content_id}")
    print(f"   - Duration:  {source.duration_seconds:.1f}s")
    print(f"   - Resolution: {source.width}x{source.height}")

    # ---- Stage 2: Content Analysis (Whisper Transcribe + AI Viral Detection) ----
    log_header("STAGE 2/6: CONTENT ANALYSIS (Whisper Transcription & Viral Moment Detection)")
    analysis_agent = ContentAnalysisAgent(db)
    r2 = analysis_agent._safe_run(source_content_id=source_content_id)
    db.commit()
    if not r2.success:
        print(f"❌ ANALYSIS FAILED: {r2.error}")
        return 1

    print(f"✅ Content Analysis Completed!")
    print(f"   - Transcript Candidates: {r2.data.get('candidates')}")
    print(f"   - Viral Moments Found:  {r2.data.get('viral_moments')}")

    # ---- Stage 3: Clip Generation (FFmpeg Video Window Cutting) ----
    log_header("STAGE 3/6: CLIP GENERATION (Cutting 9:16 Video Windows)")
    gen_agent = ClipGenerationAgent(db)
    r3 = gen_agent._safe_run(source_content_id=source_content_id)
    db.commit()
    if not r3.success or not r3.data.get("clips_created"):
        print(f"❌ CLIP GENERATION FAILED: {r3.error}")
        return 1

    clips_created = r3.data["clips_created"]
    target_clip_id = clips_created[0]
    print(f"✅ Generated {len(clips_created)} Raw Clips! Target Clip ID: {target_clip_id}")

    # ---- Stage 4: Editing & Viral Benchmark Comparison / Tag Enhancement ----
    log_header("STAGE 4/6: EDITING & VIRAL BENCHMARK COMPARISON / TAG ENHANCEMENT")
    edit_agent = EditingAgent(db)
    r4 = edit_agent._safe_run(clip_id=target_clip_id)
    db.commit()
    if not r4.success:
        print(f"❌ EDITING FAILED: {r4.error}")
        return 1

    clip = db.query(Clip).filter(Clip.id == target_clip_id).first()
    print(f"✅ Clip Editing & Viral Enhancement Completed!")
    print(f"   - Edits Applied: {r4.data.get('edits')}")
    print(f"   - Viral Alignment Score: {clip.viral_benchmark.get('overall_viral_score', 0)}% ({clip.viral_benchmark.get('tier', 'N/A')})")
    print(f"   - Hook Text: \"{clip.hook_text}\"")
    print(f"   - Enhanced Tags Suite: {clip.enhanced_tags}")
    print(f"   - Multi-Platform YouTube Title: {clip.platform_metadata.get('youtube_shorts', {}).get('title')}")
    print(f"   - Multi-Platform TikTok Caption: {clip.platform_metadata.get('tiktok', {}).get('caption')}")

    # ---- Stage 5: Quality Control ----
    log_header("STAGE 5/6: QUALITY CONTROL & AUDIT")
    qc_agent = QualityControlAgent(db)
    r5 = qc_agent._safe_run(clip_id=target_clip_id)
    db.commit()
    print(f"✅ Quality Control Evaluation: Status={clip.status}, Pass={r5.success}")

    # ---- Stage 6: Multi-Platform Publishing & Social Posting ----
    log_header("STAGE 6/6: MULTI-PLATFORM SOCIAL PUBLISHING")
    pub_agent = PublishingAgent(db)
    r6 = pub_agent._safe_run(clip_id=target_clip_id, platforms=["youtube", "tiktok", "instagram", "twitter"])
    db.commit()
    print(f"✅ Social Publishing Step Completed!")
    print(f"   - Publishing Result: {r6.data}")

    # ---- Download Finished Video to Desktop ----
    from app.core.storage import download_file
    desktop_dir = Path(os.environ.get("USERPROFILE", ".")) / "Desktop"
    output_video_path = desktop_dir / f"viral_clip_{clip.id[:8]}.mp4"
    
    try:
        download_file(clip.storage_bucket, clip.storage_key, output_video_path)
        file_size_mb = output_video_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ DOWNLOADED FINAL VIRAL CLIP TO DESKTOP: {output_video_path} ({file_size_mb:.2f} MB)")
    except Exception as exc:
        print(f"⚠️ Could not copy file to Desktop: {exc}")

    # ---- Final Summary Output ----
    log_header("FINAL PIPELINE OUTPUT & METRICS SUMMARY")
    summary = {
        "campaign_id": campaign.id,
        "clip_id": clip.id,
        "video_source_url": video_url,
        "clip_status": clip.status,
        "duration_seconds": clip.duration_seconds,
        "resolution": f"{clip.width}x{clip.height}",
        "viral_tier": clip.viral_benchmark.get("tier"),
        "viral_score_pct": clip.viral_benchmark.get("overall_viral_score"),
        "hook_detected": clip.viral_benchmark.get("hook_analysis", {}).get("detected_type"),
        "enhanced_viral_tags": clip.enhanced_tags,
        "gap_analysis": clip.viral_benchmark.get("gap_analysis"),
        "youtube_shorts_metadata": clip.platform_metadata.get("youtube_shorts"),
        "tiktok_metadata": clip.platform_metadata.get("tiktok"),
        "instagram_reels_metadata": clip.platform_metadata.get("instagram_reels"),
        "x_twitter_metadata": clip.platform_metadata.get("x_twitter"),
        "social_posts": (r6.data or {}).get("posts", []) if r6 and r6.data else [],
        "output_file": str(output_video_path) if output_video_path.exists() else clip.storage_key,
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
