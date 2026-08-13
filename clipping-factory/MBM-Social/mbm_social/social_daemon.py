import time
import sys
from pathlib import Path

# Add MBM-Social root to path so `from mbm_social import ...` works from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mbm_social import post_orchestrator


def log(msg):
    print(f"[SOCIAL DAEMON] {time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}")


def run_daemon():
    log("[SOCIAL DAEMON] Started. Watching publish_queue for real posting...")

    while True:
        try:
            summary = post_orchestrator.publish_all()
            log(f"Published {summary['published']}/{summary['processed']} package(s).")
            log("Sleeping for 15 minutes...")
            time.sleep(15 * 60)
        except KeyboardInterrupt:
            log("Shutting down daemon...")
            break
        except Exception as e:
            log(f"Daemon encountered error: {e}. Retrying in 60s...")
            time.sleep(60)


if __name__ == "__main__":
    run_daemon()
