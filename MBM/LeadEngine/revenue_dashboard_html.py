#!/usr/bin/env python3
"""
revenue_dashboard_html.py — Self-contained revenue dashboard (stdlib only)
==========================================================================
Aggregates the revenue-gate verdicts, stream targets, reply signals and
enforcer audits into a single dark-mode HTML page you can open locally,
ship as a GH artifact, or push to Telegram.

Output:
  MBM/LeadEngine/logs/revenue_dashboard.html

Usage:
  python MBM/LeadEngine/revenue_dashboard_html.py
  python MBM/LeadEngine/revenue_dashboard_html.py --out /tmp/dashboard.html
"""

import argparse
import json
import glob
import os
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"


def load(p: Path, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default if default is not None else {}


def recent_hourly_verdicts(limit=48):
    files = sorted(glob.glob(str(LOGS / "revenue" / "revenue_hourly_*.json")))
    out = []
    for f in files[-limit:]:
        d = load(Path(f), None)
        if not d:
            continue
        out.append({
            "ts": d.get("timestamp", ""),
            "answer": d.get("answer", "UNKNOWN"),
            "score": d.get("score", 0),
            "hours_no_rev": d.get("cumulative_hours_without_revenue", 0),
            "level": d.get("escalation_level", "NORMAL"),
            "deals": (d.get("signals") or {}).get("deals_won", 0),
            "meetings": (d.get("signals") or {}).get("meetings_booked", 0),
            "replies": (d.get("signals") or {}).get("replies_received", 0),
            "orders": (d.get("signals") or {}).get("paid_orders", 0),
        })
    return out


def fmt_row(v):
    ts = v["ts"][:16].replace("T", " ") if v["ts"] else "?"
    color = "#34d399" if v["answer"] == "YES" else ("#f59e0b" if v["score"] >= 60 else "#ef4444")
    return (
        f"<tr><td>{ts}</td>"
        f"<td style='color:{color};font-weight:700'>{v['answer']}</td>"
        f"<td>{v['score']}</td><td>{v['hours_no_rev']}</td>"
        f"<td>{v['deals']}</td><td>{v['meetings']}</td>"
        f"<td>{v['replies']}</td><td>{v['orders']}</td>"
        f"<td>{v['level']}</td></tr>"
    )


def build_html():
    state = load(LOGS / "revenue_state.json")
    dash = load(LOGS / "revenue_dashboard.json")
    reply = load(LOGS / "reply_summary.json")
    enforcer = load(LOGS / "enforcer_audit.json")
    seeker = load(LOGS / "seeker_opportunities.json")
    verdicts = recent_hourly_verdicts(48)

    latest = verdicts[-1] if verdicts else {}
    answer = latest.get("answer", "NO DATA")
    score = latest.get("score", 0)
    hours_no_rev = latest.get("hours_no_rev", state.get("consecutive_no_hours", 0))
    total_hours = state.get("total_hours_run", len(verdicts))
    last_yes = (state.get("last_yes_timestamp") or "NEVER")[:16].replace("T", " ")
    level = latest.get("level", "NORMAL")

    streams = dash.get("streams", [])
    total_target = dash.get("total_monthly_revenue_target", "—")
    stream_rows = ""
    for s in streams:
        stream_rows += (
            f"<tr><td>{s.get('stream','?')}</td>"
            f"<td>{s.get('type','')}</td>"
            f"<td>${s.get('monthly_revenue_target',0):,}</td>"
            f"<td>{s.get('current_status','')}</td></tr>"
        )

    rows = "".join(fmt_row(v) for v in verdicts[-24:][::-1])
    reply_count = reply.get("total_replies", 0)
    meetings = reply.get("meetings_requested", 0)
    bounces = reply.get("bounces_detected", 0)
    enforcer_status = enforcer.get("overall_status", "unknown")
    seeker_found = seeker.get("total_found", 0)

    verdict_color = "#34d399" if answer == "YES" else ("#f59e0b" if score >= 60 else "#ef4444")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BASE44 — Revenue Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0b0f19; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px; }}
  h1 {{ font-size:22px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin:20px 0; }}
  .card {{ background:#131a2b; border:1px solid #1f2a44; border-radius:12px; padding:16px; }}
  .card .label {{ color:#7c8db5; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
  .card .value {{ font-size:28px; font-weight:800; margin-top:6px; }}
  .card .sub {{ color:#64748b; font-size:12px; margin-top:4px; }}
  .verdict {{ border:1px solid {verdict_color}55; background:{verdict_color}11; }}
  .verdict .value {{ color:{verdict_color}; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #1f2a44; }}
  th {{ color:#7c8db5; text-transform:uppercase; font-size:11px; letter-spacing:.06em; }}
  .muted {{ color:#64748b; }}
  .ok {{ color:#34d399; }} .warn {{ color:#f59e0b; }} .bad {{ color:#ef4444; }}
  .footer {{ margin-top:24px; color:#475569; font-size:12px; }}
</style>
</head>
<body>
  <h1>💰 BASE44 — Revenue Dashboard</h1>
  <div class="muted" style="margin-top:4px">Last verdict: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="grid">
    <div class="card verdict">
      <div class="label">Have we made any money?</div>
      <div class="value">{answer}</div>
      <div class="sub">Escalation: {level}</div>
    </div>
    <div class="card">
      <div class="label">Revenue Gate Score</div>
      <div class="value">{score}/100</div>
      <div class="sub">Threshold 30</div>
    </div>
    <div class="card">
      <div class="label">Hours Without Revenue</div>
      <div class="value {'bad' if hours_no_rev >= 12 else ('warn' if hours_no_rev >= 6 else 'ok')}">{hours_no_rev}</div>
      <div class="sub">Total runs tracked: {total_hours}</div>
    </div>
    <div class="card">
      <div class="label">Last Revenue (YES)</div>
      <div class="value" style="font-size:18px">{last_yes}</div>
      <div class="sub">Never = no close yet</div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="label">Replies</div>
      <div class="value {('ok' if reply_count else 'bad')}">{reply_count}</div>
      <div class="sub">Meetings: {meetings} | Bounces: {bounces}</div>
    </div>
    <div class="card">
      <div class="label">Seeker Deals Found</div>
      <div class="value">{seeker_found}</div>
      <div class="sub">revenue_seeker.py total_found</div>
    </div>
    <div class="card">
      <div class="label">Enforcer Audit</div>
      <div class="value" style="font-size:18px">{enforcer_status}</div>
      <div class="sub">KPI audit overall status</div>
    </div>
    <div class="card">
      <div class="label">Monthly Target</div>
      <div class="value" style="font-size:18px">{total_target}</div>
      <div class="sub">{len(streams)} active streams</div>
    </div>
  </div>

  <h2 style="margin-top:28px;font-size:16px">Revenue Streams & Targets</h2>
  <table style="margin-top:10px">
    <thead><tr><th>Stream</th><th>Type</th><th>Monthly Target</th><th>Status</th></tr></thead>
    <tbody>{stream_rows}</tbody>
  </table>

  <h2 style="margin-top:28px;font-size:16px">Last 24 Verdicts</h2>
  <table style="margin-top:10px">
    <thead><tr><th>Time</th><th>Answer</th><th>Score</th><th>Hrs w/o $</th><th>Deals</th><th>Meetings</th><th>Replies</th><th>Orders</th><th>Level</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <div class="footer">Generated by MBM/LeadEngine/revenue_dashboard_html.py · BASE44 Control Plane</div>
</body>
</html>"""
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(LOGS / "revenue_dashboard.html"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(), encoding="utf-8")
    print(f"Revenue dashboard written to {out}")
    print(out.read_text(encoding="utf-8")[:80].replace("\n", " ").strip() + " …")


if __name__ == "__main__":
    main()
