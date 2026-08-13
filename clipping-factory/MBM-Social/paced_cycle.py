"""
paced_cycle -- one scheduled step that FEEDS the queue and PUBLISHES safely.

Replaces publish_cycle.py as the Task Scheduler entry. Differences:
  * Generation runs but can NEVER crash the task (errors logged, not fatal).
  * Publishing goes through paced_publish: max 5 posts/day, >=120 min gap,
    one brand per run. Nothing floods and channels never get flagged.
Runs on the same 15-min Task Scheduler trigger; the pace gate decides whether
a real post happens on each tick.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "mbm_social"))


def run_factory_best_effort() -> dict:
    """Try the 15-min content factory; a crash here must not brick the task."""
    try:
        from recurring_15min_video_and_agent_factory import run_15min_video_and_agent_factory

        run_15min_video_and_agent_factory()
        return {"status": "success"}
    except Exception as e:
        return {"status": "failure", "error": str(e)}


def main() -> int:
    print("=== MBM-SOCIAL PACED CYCLE ===")

    factory = run_factory_best_effort()
    if factory.get("status") == "failure":
        print(f"[CYCLE] Content factory skipped (not fatal): {factory.get('error')}")

    try:
        from mbm_social import paced_publish

        res = paced_publish.run_paced()
        try:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception:
            pass
    except Exception as e:
        print(f"[CYCLE] Paced publish error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    os.chdir(BASE)
    sys.exit(main())