"""
MBM 15-Minute Leads Run
=======================
Scheduled every 15 minutes. Runs the full skip-trace + dispatch pipeline so the
live dialer always has freshly skip-traced, gate-verified leads:

  1. skip_trace_all.py --apply --dispatch --audit
       - seller_skip_tracer (DCAD -> RapidAPI -> GMaps -> Free -> Gemini)
       - dialer_skip_trace_verifier (only genuinely unverified rows)
       - agent_lead_dispatcher (refreshes callsheet CSV + cold calling /
         multi-touch / ulio queues from the freshly traced DB)
        - dialer_verification_gate --audit
   2. seller_motivation_scorer.py --apply --sync-queues
        - Re-scores RE seller motivation tiers (offline, DCAD/311 fields only)
        - Re-sorts real_estate_calling_queue + us_re_dialer_queue tier-first
   3. Writes heartbeat + log + Output Contract report for the watchdog.

Safe by design:
  - gate-aware: already-verified rows are skipped, no API budget wasted
  - annotate-only skip tracers (apply_real_skiptrace --purge NOT enabled)
  - backups written by skip_trace_all on every --apply run

Usage:
  python MBM/Scripts/leads_15min_run.py            # full run (writes)
  python MBM/Scripts/leads_15min_run.py --dry-run  # dry run (no writes)
"""

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
LE = ROOT / "MBM" / "LeadEngine"
LOGS = BASE / "Logs"
LOGS.mkdir(parents=True, exist_ok=True)
HEARTBEAT = BASE / "Config" / "heartbeat_15min.json"
HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
REPORT = LOGS / "leads_15min_report.json"

PYTHON = sys.executable or "python"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[LEADS 15MIN] {ts} - {msg}")


def run(name, args, timeout=3600):
    cmd = [PYTHON, str(LE / args[0])] + args[1:]
    log(f">>> {name}: {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        ok = r.returncode == 0
        lines = (r.stdout + r.stderr).splitlines()
        tail = lines[-15:] if len(lines) > 15 else lines
        log(f"<<< {name}: {'OK' if ok else 'FAILED (exit %d)' % r.returncode}")
        return ok, "\n".join(tail)
    except subprocess.TimeoutExpired:
        log(f"<<< {name}: TIMEOUT")
        return False, "timeout"
    except Exception as e:
        log(f"<<< {name}: ERROR {e}")
        return False, str(e)


def db_count():
    try:
        import json as _j
        with open(ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json",
                  encoding="utf-8") as f:
            return len(_j.load(f))
    except Exception:
        return -1


def main():
    ap = argparse.ArgumentParser(description="MBM 15-Minute Leads Run")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dispatch", action="store_true", help="force dispatch even in dry-run mode")
    args = ap.parse_args()

    mode = "dry_run" if args.dry_run else "apply"
    log("=" * 60)
    log(f"  15-MINUTE LEADS RUN ({mode})")
    log("=" * 60)

    db_before = db_count()
    log(f"DB before: {db_before} leads")

    orc_args = ["skip_trace_all.py", "--dispatch", "--audit"]
    if not args.dry_run:
        orc_args.append("--apply")
    # NOTE: agent_lead_dispatcher (inside skip_trace_all) already exports ALL
    # gate-verified DB leads to npi_verified_callsheet.csv. Running
    # npi_verified_callsheet.py here would CLOBBER that full callsheet with a
    # smaller fresh pull and drop 100% gate coverage — so it is intentionally
    # not part of the 15-min cycle. Fresh NPI discovery runs on its own
    # hourly/daily schedule (npm run leads:callsheet).
    ok, out = run("Skip-Trace Orchestrator", orc_args)
    steps = [{"step": "skip_trace_all", "ok": ok, "output_tail": out}]

    # 2. Re-score seller motivation tiers + re-sync the RE dialer queues.
    #    Scores derive only from already-verified DCAD/311 fields (no network),
    #    and --sync-queues rewrites the RE queues tier-sorted so the dialer
    #    works the strongest sellers first.
    mot_args = ["seller_motivation_scorer.py", "--apply", "--sync-queues"]
    if args.dry_run:
        mot_args = ["seller_motivation_scorer.py"]  # dry-run = no writes
    ok, out = run("Seller Motivation Scorer", mot_args)
    steps.append({"step": "seller_motivation_scorer", "ok": ok, "output_tail": out})

    db_after = db_count()

    report = {
        "status": "success" if all(s["ok"] for s in steps) else "failure",
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {"dry_run": args.dry_run},
        "outputs": {"db_before": db_before, "db_after": db_after},
        "steps": steps,
        "next_action": "open mbm-dialer app -> leads are gate-verified & dialable",
        "owner": "system",
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hb = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if report["status"] == "success" else "degraded",
        "last_log": str(REPORT),
        "db_leads": db_after,
    }
    HEARTBEAT.write_text(json.dumps(hb, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"  15-MIN LEADS RUN COMPLETE ({mode})")
    print("=" * 60)
    for s in steps:
        print(f"  [{'OK' if s['ok'] else 'FAIL'}] {s['step']}")
    print(f"  DB: {db_before} -> {db_after}")
    print(f"  Report: {REPORT}")
    sys.exit(0 if report["status"] == "success" else 1)


if __name__ == "__main__":
    main()
