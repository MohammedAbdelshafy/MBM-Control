"""
publish_cycle -- one scheduled step: produce new clip drafts, then really publish
anything pending in publish_queue. Run on a 15-minute cadence via Windows Task
Scheduler (JarvisOS_15Min_VideoAgentFactory).

Generation only ever writes `status: draft` packages. The orchestrator is the
only component that flips a package to `published`, and it only does so after a
real upload succeeds on at least one platform.
"""
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "mbm_social"))

from mbm_social import post_orchestrator


def main() -> int:
    print("=== MBM-SOCIAL PUBLISH CYCLE ===")
    try:
        from recurring_15min_video_and_agent_factory import run_15min_video_and_agent_factory
        run_15min_video_and_agent_factory()
    except Exception as e:
        print(f"[CYCLE] Content factory skipped: {e}")

    summary = post_orchestrator.publish_all()
    print(f"[CYCLE] Published {summary['published']}/{summary['processed']} package(s).")
    try:
        print(json.dumps(summary, indent=2))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    os.chdir(BASE)
    sys.exit(main())