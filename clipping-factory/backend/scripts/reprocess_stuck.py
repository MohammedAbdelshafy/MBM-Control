"""
Reprocess stuck clips — reset clips stuck in 'editing' status and re-queue for editing.
"""
import sys
sys.path.insert(0, ".")

from app.core.database import SyncSessionLocal
from app.models.clip import Clip, ClipStatus

db = SyncSessionLocal()
try:
    stuck = db.query(Clip).filter(Clip.status.in_(["editing", "qc_pending"])).all()
    print(f"Found {len(stuck)} stuck clips")

    reset_count = 0
    for clip in stuck:
        # Check if the clip has raw file (not edited yet)
        if clip.edits_applied and len(clip.edits_applied) > 0:
            # Already edited, just reset to qc_pending
            clip.status = ClipStatus.QC_PENDING
        else:
            # Never edited, reset to generating so it gets re-processed
            clip.status = ClipStatus.GENERATING
        reset_count += 1

    db.commit()
    print(f"Reset {reset_count} clips")

    # Now re-queue editing for clips that need it
    from app.workers.video_tasks import edit_clip, quality_check_clip

    needs_edit = db.query(Clip).filter(Clip.status == ClipStatus.GENERATING).limit(50).all()
    print(f"Re-queuing {len(needs_edit)} clips for editing")

    for clip in needs_edit:
        clip.status = ClipStatus.EDITING
        db.flush()
        try:
            edit_clip.apply_async(args=[clip.id], queue="video")
            print(f"  Queued: {clip.id[:8]}")
        except Exception as e:
            print(f"  Failed to queue {clip.id[:8]}: {e}")

    needs_qc = db.query(Clip).filter(Clip.status == ClipStatus.QC_PENDING).limit(50).all()
    print(f"Re-queuing {len(needs_qc)} clips for editor QA")

    for clip in needs_qc:
        try:
            quality_check_clip.apply_async(args=[clip.id], queue="video")
            print(f"  Queued QC: {clip.id[:8]}")
        except Exception as e:
            print(f"  Failed to queue QC {clip.id[:8]}: {e}")

    db.commit()
    print("Done!")

finally:
    db.close()
