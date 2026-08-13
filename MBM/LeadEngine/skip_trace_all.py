"""
MBM Master Skip-Trace Orchestrator
==================================
Runs EVERY skiptracing tool in the pipeline in sequence against the live
dialer database (mbm-dialer/app/public/leads_database.json). Designed to be
invoked from scheduled runs (4-hr engine, daily cycle, hourly CI, npm script).

Pipeline:
  1. seller_skip_tracer.py --apply --resume
       Hybrid DCAD -> RapidAPI -> GMaps -> Free scrapers -> Gemini.
       Only targets Real Estate Sellers / Texas Real Estate / Master Catch-All.
       Never deletes rows, only annotates with real proof.
  2. dialer_skip_trace_verifier.py
       RapidAPI Skip Tracing + FreeSkipTracer multi-source verifier.
       Processes the next BATCH_SIZE unverified leads (annotate-only).
  3. apply_real_skiptrace.py  (only with --purge)
       FreeSkipTracer ensurement that DROPS rows it cannot verify against a
       real number. Opt-in for scheduled runs because it deletes rows.

  Optional: --dispatch re-runs agent_lead_dispatcher.py so every agent queue
            (callsheet CSV, cold calling, multi-touch, ulio) is refreshed from
            the freshly traced DB. --audit runs the dialer verification gate.

Usage:
  python MBM/LeadEngine/skip_trace_all.py                 # dry-run (NO writes)
  python MBM/LeadEngine/skip_trace_all.py --apply
  python MBM/LeadEngine/skip_trace_all.py --apply --dispatch --audit
  python MBM/LeadEngine/skip_trace_all.py --apply --purge --limit 25
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REPORT = LOGS / "skip_trace_all_report.json"

PYTHON = sys.executable or "python"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[SKIPTRACE ALL] {ts} - {msg}")


def run_step(name, script, args, timeout=3600):
    """Run one pipeline tool; returns (success, output)."""
    cmd = [PYTHON, str(BASE / script)] + args
    log(f">>> [{name}] running: {' '.join(cmd)}")
    start = datetime.now()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        ok = result.returncode == 0
        out = result.stdout + result.stderr
        if not ok:
            log(f"<<< [{name}] FAILED (exit {result.returncode})")
        else:
            log(f"<<< [{name}] OK")
        # Keep tail of output for the report
        lines = out.splitlines()
        tail = lines[-25:] if len(lines) > 25 else lines
        return ok, "\n".join(tail)
    except subprocess.TimeoutExpired:
        log(f"<<< [{name}] TIMEOUT after {timeout}s")
        return False, f"timeout after {timeout}s"
    except Exception as e:
        log(f"<<< [{name}] ERROR: {e}")
        return False, str(e)


def backup_db():
    if not DIALER_DB.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Backups go OUTSIDE the served app/public dir — writing .bak files into the
    # Vite-watched public folder crashes the dev server (EBUSY watcher).
    bak_dir = BASE / "logs" / "db_backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    bak = bak_dir / f"leads_database.{stamp}.bak.json"
    shutil.copy2(DIALER_DB, bak)
    log(f"[backup] wrote {bak}")
    return str(bak)


def count_unverified():
    """Count leads that do NOT pass the dialer verification gate.

    Uses the real gate (dialer_verification_gate.check_lead) so NPI-registry
    clinics count as verified even though they carry no skip_trace_status.
    """
    try:
        sys.path.insert(0, str(BASE))
        from dialer_verification_gate import check_lead
    except Exception:
        check_lead = None
    try:
        with open(DIALER_DB, "r", encoding="utf-8") as f:
            db = json.load(f)
        if check_lead is None:
            return -1
        return sum(1 for l in db if not check_lead(l).get("passed"))
    except Exception:
        return -1


def main():
    ap = argparse.ArgumentParser(description="MBM Master Skip-Trace Orchestrator")
    ap.add_argument("--apply", action="store_true", help="write results (default: dry-run)")
    ap.add_argument("--purge", action="store_true",
                    help="also run apply_real_skiptrace.py (DROPS unverifiable rows)")
    ap.add_argument("--limit", type=int, default=None,
                    help="limit leads for seller_skip_tracer (and purge)")
    ap.add_argument("--batch-size", type=int, default=100,
                    help="BATCH_SIZE for dialer_skip_trace_verifier (default 100)")
    ap.add_argument("--dispatch", action="store_true",
                    help="re-run agent_lead_dispatcher.py after tracing")
    ap.add_argument("--audit", action="store_true",
                    help="run dialer_verification_gate.py --audit after tracing")
    ap.add_argument("--no-free", action="store_true",
                    help="skip free web scrapers in seller_skip_tracer")
    ap.add_argument("--no-gemini", action="store_true",
                    help="skip gemini fallback in seller_skip_tracer")
    args = ap.parse_args()

    mode = "apply" if args.apply else "dry_run"
    log("=" * 60)
    log(f"  MASTER SKIP-TRACE ORCHESTRATOR ({mode})")
    log("=" * 60)

    if not DIALER_DB.exists():
        log(f"ERROR: {DIALER_DB} missing — abort.")
        REPORT.write_text(json.dumps({
            "status": "failure", "error": "leads_database.json missing",
        }, indent=2), encoding="utf-8")
        sys.exit(1)

    db_before = 0
    try:
        with open(DIALER_DB, "r", encoding="utf-8") as f:
            db_before = len(json.load(f))
    except Exception:
        pass
    unverified_before = count_unverified()
    log(f"DB: {db_before} leads, {unverified_before} unverified before run")

    backup_path = None
    if args.apply:
        backup_path = backup_db()

    steps = []

    # Step 1: Hybrid seller skip tracer (annotate-only, safe).
    st_args = ["--apply"] if args.apply else []
    st_args += ["--resume", "--vertical", "Real Estate Sellers,Texas Real Estate,Master Catch-All"]
    if args.no_free:
        st_args.append("--no-free")
    if args.no_gemini:
        st_args.append("--no-gemini")
    if args.limit:
        st_args += ["--limit", str(args.limit)]
    ok, out = run_step("Seller Skip Tracer", "seller_skip_tracer.py", st_args)
    steps.append({"step": "seller_skip_tracer", "ok": ok, "output_tail": out})

    # Step 2: Multi-source dialer skip trace verifier (annotate-only).
    ok, out = run_step("Dialer Skip Trace Verifier", "dialer_skip_trace_verifier.py", [])
    steps.append({"step": "dialer_skip_trace_verifier", "ok": ok, "output_tail": out})

    # Step 3 (optional): FreeSkipTracer ensurement — DROPS unverifiable rows.
    if args.purge:
        ok, out = run_step("Apply Real Skip Trace (purge)", "apply_real_skiptrace.py", [])
        steps.append({"step": "apply_real_skiptrace", "ok": ok, "output_tail": out})
    else:
        log("[skip] apply_real_skiptrace.py not run (add --purge to enable row-dropping ensurement)")

    # Post-tracing counts.
    db_after = 0
    try:
        with open(DIALER_DB, "r", encoding="utf-8") as f:
            db_after = len(json.load(f))
    except Exception:
        pass
    unverified_after = count_unverified()
    log(f"DB after tracing: {db_after} leads, {unverified_after} unverified")

    # Optional: re-dispatch all agent queues.
    if args.dispatch:
        ok, out = run_step("Agent Lead Dispatcher", "agent_lead_dispatcher.py", [])
        steps.append({"step": "agent_lead_dispatcher", "ok": ok, "output_tail": out})

    # Optional: gate audit.
    gate_result = None
    if args.audit:
        ok, out = run_step("Dialer Verification Gate", "dialer_verification_gate.py", ["--audit"])
        steps.append({"step": "dialer_verification_gate", "ok": ok, "output_tail": out})
        try:
            audit_file = BASE / "logs" / "gate_audit.json"
            if audit_file.exists():
                gate_result = json.loads(audit_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    all_ok = all(s["ok"] for s in steps if s["step"] != "apply_real_skiptrace")
    report = {
        "status": "success" if all_ok else "failure",
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "purge": args.purge, "dispatch": args.dispatch, "audit": args.audit,
            "batch_size": args.batch_size, "limit": args.limit,
        },
        "outputs": {
            "db_before": db_before,
            "db_after": db_after,
            "unverified_before": unverified_before,
            "unverified_after": unverified_after,
            "backup": backup_path,
            "gate": gate_result,
        },
        "steps": steps,
        "next_action": "agent_lead_dispatcher.py -- then close_queue_dialer.py for live dialing",
        "owner": "system",
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"  SKIP-TRACE ORCHESTRATOR COMPLETE ({mode})")
    print("=" * 60)
    for s in steps:
        print(f"  [{'OK' if s['ok'] else 'FAIL'}] {s['step']}")
    print(f"  DB: {db_before} -> {db_after}  |  unverified: {unverified_before} -> {unverified_after}")
    print(f"  Report: {REPORT}")
    print()
    if not args.apply:
        print("  DRY-RUN — no writes. Re-run with --apply.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
