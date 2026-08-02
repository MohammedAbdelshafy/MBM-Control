"""
Revenue Tracker — Hourly Revenue Accountability Gate
=====================================================
Every hourly run asks: "Have we made any money?"
If YES → log + continue.
If NO  → auto-adjust markets, targets, templates + log.

Escalation ladder:
  - 6 consecutive NO → CRITICAL alert + breakup templates
  - 12 consecutive NO → full pause + HUMAN_REVIEW_REQUIRED
"""

import os
import sys
import json
import glob
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
REVENUE_LOG_DIR = LOGS_DIR / 'revenue'
AUDIT_FILE = LOGS_DIR / 'revenue_audit_log.json'
STATE_FILE = LOGS_DIR / 'revenue_state.json'
QUEUE_FILE = BASE_DIR / 'cold_calling_queue.json'
OUTREACH_LOG = BASE_DIR / 'outreach_log.json'
CADENCE_LOG = LOGS_DIR / 'cadence_history.json'
ENRICHED_LEADS = BASE_DIR / 'enriched_global_leads.json'
REPLY_SUMMARY = LOGS_DIR / 'reply_summary.json'

REVENUE_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Scoring Weights ───
WEIGHTS = {
    "deals_won":          100,   # Instant YES
    "meetings_booked":     60,   # Money is imminent
    "replies_received":    30,   # Warm pipeline
    "contacts_verified":    8,   # Per verified contact
    "outreach_volume":      2,   # Per email/call sent
}

YES_THRESHOLD = 30   # Score ≥ 30 = "YES, we made money"

# CRM dispositions that map to each revenue signal
DISPOSITION_MAP = {
    "deals_won":       {"won", "closed", "deal_signed", "recurring_customer"},
    "meetings_booked": {"meeting_booked", "negotiating"},
    "replies_received": {"called", "linkedin", "replied"},
}

# Market rotation for expansion when NO
MARKET_ROTATION = [
    "sheffield", "nottingham", "glasgow", "edinburgh", "cardiff",
    "bristol", "leicester", "dublin", "lisbon", "milan",
    "chicago", "houston", "phoenix", "philadelphia", "san antonio",
]


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[REVENUE TRACKER] {timestamp} - {msg}"
    # Windows cp1252 can't print emoji — encode safely
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))
    log_file = LOGS_DIR / 'revenue_tracker.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


class RevenueTracker:
    """Hourly revenue accountability engine."""

    def __init__(self):
        self.state = self._load_state()

    # ─── State Persistence ───

    def _load_state(self):
        default = {
            "consecutive_no_hours": 0,
            "total_hours_run": 0,
            "last_yes_timestamp": None,
            "pending_adjustments": {},
            "paused": False,
        }
        saved = _load_json(STATE_FILE, default)
        for k, v in default.items():
            saved.setdefault(k, v)
        return saved

    def _save_state(self):
        _save_json(STATE_FILE, self.state)

    # ─── Signal Collection ───

    def _count_dispositions(self):
        """Read cold_calling_queue.json and tally dispositions."""
        data = _load_json(QUEUE_FILE)
        queue = data.get("queue", []) if isinstance(data, dict) else data

        signals = {
            "deals_won": 0,
            "meetings_booked": 0,
            "replies_received": 0,
        }

        for item in queue:
            d = (item.get("disposition") or "none").lower().strip()
            for signal, valid_disps in DISPOSITION_MAP.items():
                if d in valid_disps:
                    signals[signal] += 1

        return signals

    def _count_contacts_verified(self):
        """Count leads with both verified phone and email."""
        leads = _load_json(ENRICHED_LEADS, [])
        if not isinstance(leads, list):
            return 0
        count = 0
        for lead in leads:
            phone = lead.get("phone") or lead.get("agent_phone")
            email = lead.get("email") or lead.get("agent_email")
            if phone and email:
                count += 1
        return count

    def _count_real_replies(self):
        """Real, human replies detected by reply_detector.py (not queue placeholders)."""
        s = _load_json(REPLY_SUMMARY, {})
        return {
            "replies_received": int(s.get("total_replies", 0) or 0),
            "meetings_booked": int(s.get("meetings_requested", 0) or 0),
        }

    def _count_paid_orders(self):
        """REAL money: count paid orders in the client_orders table."""
        try:
            import requests
            from dotenv import load_dotenv
            load_dotenv(BASE_DIR.parent.parent / ".env.local")
            url = os.getenv("VITE_SUPABASE_URL", "https://prgmwljhbjtcjmwnjaao.supabase.co")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            if not key:
                return 0
            r = requests.get(
                f"{url}/rest/v1/client_orders",
                params={"select": "id", "status": "eq.paid", "limit": "1000"},
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=20,
            )
            if r.status_code >= 400:
                return 0
            return len(r.json())
        except Exception:
            return 0

    def _count_outreach_volume(self):
        """Count total outreach actions (emails sent + cadence touches)."""
        outreach = _load_json(OUTREACH_LOG, [])
        outreach_count = len(outreach) if isinstance(outreach, list) else 0

        cadence = _load_json(CADENCE_LOG)
        cadence_count = sum(
            r.get("touches", 0) for r in cadence.values()
        ) if isinstance(cadence, dict) else 0

        return outreach_count + cadence_count

    def collect_signals(self):
        """Gather all 5 revenue signals from the current pipeline state."""
        disps = self._count_dispositions()
        real = self._count_real_replies()
        paid = self._count_paid_orders()
        # Real money: paid client_orders OR a won/closed disposition in the queue.
        # Placeholder queue dispositions alone can be gameable — paid orders cannot.
        deals = max(disps["deals_won"], paid)
        return {
            "deals_won":         deals,
            "meetings_booked":   max(disps["meetings_booked"], real["meetings_booked"]),
            "replies_received":  max(disps["replies_received"], real["replies_received"]),
            "contacts_verified": self._count_contacts_verified(),
            "outreach_volume":   self._count_outreach_volume(),
            "paid_orders":       paid,
        }

    # ─── Scoring Engine ───

    def compute_score(self, signals):
        """Weighted revenue score from collected signals."""
        score = 0
        score += signals["deals_won"]       * WEIGHTS["deals_won"]
        score += signals["meetings_booked"] * WEIGHTS["meetings_booked"]
        score += signals["replies_received"] * WEIGHTS["replies_received"]
        score += signals["contacts_verified"] * WEIGHTS["contacts_verified"]
        score += signals["outreach_volume"]  * WEIGHTS["outreach_volume"]
        return score

    # ─── The Question ───

    def hourly_revenue_check(self):
        """
        THE QUESTION: "Have we made any money?"

        Returns:
            dict with keys: made_money, answer, score, signals,
                            adjustments, escalation_level, output_contract
        """
        if self.state.get("paused"):
            log("⛔ PIPELINE PAUSED — HUMAN_REVIEW_REQUIRED. Skipping revenue check.")
            return {
                "made_money": False,
                "answer": "PAUSED — HUMAN REVIEW REQUIRED",
                "score": 0,
                "signals": {},
                "adjustments": [],
                "escalation_level": "PAUSED",
                "output_contract": self._output_contract(
                    "skipped", {}, {}, ["Pipeline paused after 12h of no revenue"],
                    "human_review", owner="human"
                ),
            }

        signals = self.collect_signals()
        score = self.compute_score(signals)
        # THE REAL MONEY GATE: only a won/closed/signed deal counts as money.
        # Meetings, replies, verified contacts, and outreach volume are pipeline
        # activity — they feed the score for tracking but never flip the verdict.
        made_money = signals["deals_won"] >= 1

        self.state["total_hours_run"] += 1
        hour_number = self.state["total_hours_run"]

        adjustments = []
        escalation = "NORMAL"

        if made_money:
            # ─── YES ───
            log(f"✅ HOUR {hour_number} — YES, we made money. "
                f"Deals won: {signals['deals_won']}. Pipeline score: {score}")
            self.state["consecutive_no_hours"] = 0
            self.state["last_yes_timestamp"] = datetime.now(timezone.utc).isoformat()
            # Clear any pending adjustments since things are working
            self.state["pending_adjustments"] = {}
        else:
            # ─── NO ───
            self.state["consecutive_no_hours"] += 1
            no_hours = self.state["consecutive_no_hours"]
            log(f"❌ HOUR {hour_number} — NO revenue. Deals won: {signals['deals_won']}. "
                f"Pipeline score: {score}. Consecutive NO hours: {no_hours}")

            adjustments = self._generate_adjustments(no_hours, signals)
            self.state["pending_adjustments"] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "adjustments": adjustments,
            }

            # Real replies exist but no deal closed yet → the money is sitting in
            # the inbox. This is the highest-ROI moment: a human must respond.
            if signals["replies_received"] > 0:
                escalation = "HUMAN_ACTION_REQUIRED"
                adjustments.append({
                    "type": "human_meeting_required",
                    "description": (
                        f"{signals['replies_received']} real reply/replies are waiting — "
                        f"a human must respond and book the meeting. No deal is possible "
                        f"until a conversation happens."
                    ),
                    "action": "human_followup",
                    "value": signals["replies_received"],
                })
                log(f"🫱 {signals['replies_received']} REPLY/REPLIES WAITING — "
                    f"owner=human — respond to close the deal")

            if no_hours >= 12:
                escalation = "PAUSED"
                self.state["paused"] = True
                log("⛔ 12 CONSECUTIVE HOURS WITHOUT REVENUE — PAUSING PIPELINE")
                log("⛔ owner=human — HUMAN_REVIEW_REQUIRED")
            elif no_hours >= 6:
                escalation = "CRITICAL"
                log("🚨 6 CONSECUTIVE HOURS WITHOUT REVENUE — CRITICAL ESCALATION")

        # Write hourly report
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hour_number": hour_number,
            "question": "Have we made any money?",
            "answer": "YES" if made_money else "NO",
            "score": score,
            "threshold": YES_THRESHOLD,
            "signals": signals,
            "adjustments_applied": adjustments,
            "escalation_level": escalation,
            "cumulative_hours_without_revenue": self.state["consecutive_no_hours"],
        }

        self._write_hourly_report(report)
        self._append_audit(report)
        self._save_state()

        human_needed = (
            not made_money
            and signals.get("replies_received", 0) > 0
        )
        return {
            "made_money": made_money,
            "answer": "YES" if made_money else "NO",
            "score": score,
            "signals": signals,
            "adjustments": adjustments,
            "escalation_level": escalation,
            "output_contract": self._output_contract(
                "success" if made_money else "failure",
                {"hour": hour_number},
                report,
                [] if made_money else [f"No revenue for {self.state['consecutive_no_hours']}h"],
                "human_followup" if human_needed else ("continue" if made_money else "adjust_strategy"),
                owner="human" if (human_needed or escalation == "PAUSED") else "system",
            ),
        }

    # ─── Auto-Adjustments ───

    def _generate_adjustments(self, no_hours, signals):
        """Generate corrective actions based on how long revenue has been zero."""
        adjustments = []

        # ─── Standard adjustments (hours 1-5) ───
        if signals["outreach_volume"] < 10:
            adjustments.append({
                "type": "increase_outreach",
                "description": "Outreach volume below 10. Increasing target_deals by 50%",
                "action": "target_deals_multiplier",
                "value": 1.5,
            })

        if signals["contacts_verified"] < 5:
            adjustments.append({
                "type": "expand_markets",
                "description": f"Low contact verification. Adding 2 new markets from rotation",
                "action": "add_markets",
                "value": self._pick_new_markets(2),
            })

        if no_hours >= 3:
            adjustments.append({
                "type": "urgency_templates",
                "description": "3h without revenue. Switching to high-urgency outreach templates",
                "action": "template_mode",
                "value": "urgency",
            })

        # ─── Critical escalation (hours 6-11) ───
        if no_hours >= 6:
            adjustments.append({
                "type": "breakup_templates",
                "description": "6h without revenue. CRITICAL — switching to breakup/final-notice templates",
                "action": "template_mode",
                "value": "breakup",
            })
            adjustments.append({
                "type": "expand_markets_aggressive",
                "description": "Aggressive market expansion — adding 4 new cities",
                "action": "add_markets",
                "value": self._pick_new_markets(4),
            })
            adjustments.append({
                "type": "increase_outreach_aggressive",
                "description": "Doubling target deals",
                "action": "target_deals_multiplier",
                "value": 2.0,
            })

        return adjustments

    def _pick_new_markets(self, count):
        """Pick cities from rotation that aren't already in the current run."""
        state_markets = self.state.get("_active_markets", [])
        available = [m for m in MARKET_ROTATION if m not in state_markets]
        picked = available[:count]
        # Track to avoid re-picking
        self.state.setdefault("_active_markets", []).extend(picked)
        return picked

    def apply_pending_adjustments(self):
        """
        Called at the START of each hourly cycle.
        Reads pending adjustments and returns config overrides for the pipeline.
        """
        pending = self.state.get("pending_adjustments", {})
        adjustments = pending.get("adjustments", [])

        if not adjustments:
            return {
                "target_deals": 30,
                "extra_markets": [],
                "template_mode": "standard",
            }

        config = {
            "target_deals": 30,
            "extra_markets": [],
            "template_mode": "standard",
        }

        for adj in adjustments:
            action = adj.get("action")
            value = adj.get("value")

            if action == "target_deals_multiplier":
                config["target_deals"] = int(config["target_deals"] * value)

            elif action == "add_markets":
                if isinstance(value, list):
                    config["extra_markets"].extend(value)

            elif action == "template_mode":
                # Higher urgency always wins
                urgency_order = {"standard": 0, "urgency": 1, "breakup": 2}
                if urgency_order.get(value, 0) > urgency_order.get(config["template_mode"], 0):
                    config["template_mode"] = value

        log(f"ADJUSTMENTS APPLIED: target={config['target_deals']}, "
            f"extra_markets={config['extra_markets']}, "
            f"template={config['template_mode']}")

        return config

    def unpause(self):
        """Manual unpause after human review."""
        self.state["paused"] = False
        self.state["consecutive_no_hours"] = 0
        self.state["pending_adjustments"] = {}
        self._save_state()
        log("🔓 Pipeline UNPAUSED by human operator.")

    # ─── Reporting ───

    def _write_hourly_report(self, report):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = REVENUE_LOG_DIR / f"revenue_hourly_{stamp}.json"
        _save_json(path, report)
        log(f"Hourly revenue report: {path.name}")

        # Prune old reports (keep last 168 = 7 days)
        reports = sorted(REVENUE_LOG_DIR.glob("revenue_hourly_*.json"))
        while len(reports) > 168:
            reports[0].unlink()
            reports = reports[1:]

    def _append_audit(self, report):
        audit = _load_json(AUDIT_FILE, [])
        if not isinstance(audit, list):
            audit = []
        audit.append(report)
        # Keep last 720 entries (30 days)
        if len(audit) > 720:
            audit = audit[-720:]
        _save_json(AUDIT_FILE, audit)

    def _output_contract(self, status, inputs, outputs, errors, next_action, owner="system"):
        return {
            "status": status,
            "inputs": inputs,
            "outputs": outputs,
            "errors": errors,
            "next_action": next_action,
            "owner": owner,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Analytics ───

    def get_revenue_summary(self):
        """Return a summary of revenue performance for dashboards."""
        audit = _load_json(AUDIT_FILE, [])
        if not isinstance(audit, list):
            audit = []

        total_checks = len(audit)
        yes_count = sum(1 for r in audit if r.get("answer") == "YES")
        no_count = sum(1 for r in audit if r.get("answer") == "NO")
        avg_score = (sum(r.get("score", 0) for r in audit) / total_checks) if total_checks > 0 else 0

        return {
            "total_hourly_checks": total_checks,
            "yes_count": yes_count,
            "no_count": no_count,
            "yes_rate": f"{(yes_count / total_checks * 100):.1f}%" if total_checks > 0 else "N/A",
            "avg_score": round(avg_score, 1),
            "current_consecutive_no": self.state.get("consecutive_no_hours", 0),
            "pipeline_paused": self.state.get("paused", False),
            "last_yes": self.state.get("last_yes_timestamp", "Never"),
        }


# ─── CLI / Self-Test ───

def _run_self_test():
    """Self-test with current pipeline data."""
    print("=" * 60)
    print("REVENUE TRACKER — SELF-TEST")
    print("=" * 60)

    tracker = RevenueTracker()

    print("\n1. Collecting signals...")
    signals = tracker.collect_signals()
    for k, v in signals.items():
        print(f"   {k}: {v}")

    print("\n2. Computing score...")
    score = tracker.compute_score(signals)
    print(f"   Score: {score} (pipeline health, threshold: {YES_THRESHOLD})")
    print(f"   Answer: {'YES' if signals['deals_won'] >= 1 else 'NO'} "
          f"(money gate = deals_won >= 1, current: {signals['deals_won']})")

    print("\n3. Running full revenue check...")
    verdict = tracker.hourly_revenue_check()
    print(f"   Made money: {verdict['made_money']}")
    print(f"   Answer: {verdict['answer']}")
    print(f"   Escalation: {verdict['escalation_level']}")
    if verdict['adjustments']:
        print(f"   Adjustments:")
        for adj in verdict['adjustments']:
            print(f"     - {adj['description']}")

    print("\n4. Revenue summary:")
    summary = tracker.get_revenue_summary()
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("SELF-TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Revenue Tracker — Have we made money?")
    parser.add_argument("command", nargs="?", default="check",
                        choices=["check", "test", "summary", "unpause"],
                        help="check (run revenue gate), test (self-test), summary, unpause")
    args = parser.parse_args()

    if args.command == "test":
        _run_self_test()
    elif args.command == "check":
        tracker = RevenueTracker()
        result = tracker.hourly_revenue_check()
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "summary":
        tracker = RevenueTracker()
        print(json.dumps(tracker.get_revenue_summary(), indent=2))
    elif args.command == "unpause":
        tracker = RevenueTracker()
        tracker.unpause()
        print("Pipeline unpaused.")
