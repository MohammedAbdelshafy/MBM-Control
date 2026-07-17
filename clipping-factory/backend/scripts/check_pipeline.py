from app.core.database import SyncSessionLocal
from app.models.clip import Clip
from app.models.campaign import Campaign

db = SyncSessionLocal()
try:
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).limit(5).all()
    print("=== RECENT CAMPAIGNS ===")
    for c in campaigns:
        clips = db.query(Clip).filter(Clip.campaign_id == c.id).all()
        statuses = {}
        for cl in clips:
            statuses[cl.status] = statuses.get(cl.status, 0) + 1
        title = (c.title[:50] if c.title else "Untitled")
        print(f"  {title} ({c.id[:8]}) - {len(clips)} clips: {statuses}")

    clips = db.query(Clip).order_by(Clip.created_at.desc()).limit(15).all()
    print()
    print("=== RECENT CLIPS ===")
    for cl in clips:
        score = cl.overall_score or 0
        edits = cl.edits_applied or []
        dur = cl.duration_seconds or 0
        print(f"  {cl.id[:8]} | {cl.status:20s} | score={score:.2f} | edits={len(edits)} | {dur:.1f}s")

    stuck = db.query(Clip).filter(Clip.status.in_(["qc_pending", "editing"])).count()
    print(f"\nStuck in qc_pending/editing: {stuck}")
    failed = db.query(Clip).filter(Clip.status == "qc_fail").count()
    print(f"Failed QC: {failed}")

    # Check editor QA scores
    high_quality = db.query(Clip).filter(Clip.overall_score >= 0.85).count()
    mid_quality = db.query(Clip).filter(Clip.overall_score >= 0.65, Clip.overall_score < 0.85).count()
    low_quality = db.query(Clip).filter(Clip.overall_score < 0.65, Clip.overall_score > 0).count()
    print(f"\nQuality distribution: >=0.85: {high_quality} | 0.65-0.84: {mid_quality} | <0.65: {low_quality}")
finally:
    db.close()
