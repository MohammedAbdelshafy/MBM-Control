"""
WHOP FIRST REVENUE CAMPAIGN — whop_audit_day1
=============================================
Builds and tracks the controlled 25-prospect experiment whose objective is the
FIRST VERIFIED PURCHASE of the Revenue Audit Engine ($149, prod_L2MmMKYlE9LAv).

Prospect source (ONLY legitimate source allowed):
    MBM/Artifacts/GTM_TOP25_EXECUTION_QUEUE.json  (CMS NPI Registry verified)

Outputs (artifact-only; nothing is ever auto-sent):
    MBM/Artifacts/GTM/campaigns/whop_audit_day1/
      campaign.json      config + offer + links
      prospects.csv      per-prospect rows (mission schema)
      DAY1_PLAYBOOK.md   human-run 1-click WhatsApp / Gmail links per prospect
      state.json         status ledger (contacted/replied/checkout/purchase)
      contact_log.jsonl  append-only outreach log (duplicate guard)

CLI:
  python MBM/Whop/whop_first_revenue_campaign.py build [--base-url URL] [--limit N]
  python MBM/Whop/whop_first_revenue_campaign.py mark <prospect_id> --status contacted|replied|checkout_started|purchased [--note "..."]
  python MBM/Whop/whop_first_revenue_campaign.py funnel     # stage counts + leak diagnosis (Phase 13)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
QUEUE_JSON = ROOT_DIR / "MBM" / "Artifacts" / "GTM_TOP25_EXECUTION_QUEUE.json"
CAMPAIGN_DIR = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "campaigns" / "whop_audit_day1"
EVENTS_LOG = BASE_DIR / "logs" / "revenue_events.jsonl"

DEFAULT_BASE_URL = "https://mbm-dialer-app.vercel.app"
LANDING_PATH = "/productized-service/ai-consultancy-sprint/landing.html#engines"
CHECKOUT_URL = "https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ"

OFFER = {
    "campaign": "whop_audit_day1",
    "objective": "FIRST_VERIFIED_PURCHASE",
    "product": "Revenue Audit Engine",
    "product_id": "prod_L2MmMKYlE9LAv",
    "plan_id": "plan_Sg0oIq3Tf4rlQ",
    "price_usd": 149,
    "promise": "72-hour revenue leakage audit: we map your lead-to-revenue pipeline and hand you a ranked fix list.",
}

FOLLOW_UP_SCHEDULE = [
    {"day": 3, "channel": "same_as_first_touch", "cap": 1,
     "rule": "only if no reply; reference original message; no new pitch"},
    {"day": 7, "channel": "same_as_first_touch", "cap": 1,
     "rule": "final touch; 'closing the loop' framing; then stop permanently"},
]
MAX_TOUCHES_PER_PROSPECT = 3

STATUSES = ["pending", "contacted", "replied", "checkout_started", "purchased", "opted_out"]
STAGE_ORDER = ["generated", "contacted", "replied", "checkout_started", "purchased"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def _load_state() -> dict:
    f = CAMPAIGN_DIR / "state.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"schema_version": 1, "updated_at": None, "prospects": {}}


def _save_state(state: dict) -> None:
    state["updated_at"] = _now()
    _atomic_write(CAMPAIGN_DIR / "state.json", json.dumps(state, indent=2))


def landing_url(base_url: str, prospect_id: str) -> str:
    q = urllib.parse.urlencode({
        "utm_source": "outreach",
        "utm_medium": "direct",
        "utm_campaign": OFFER["campaign"],
        "utm_content": prospect_id,
    })
    sep = "&" if "?" in LANDING_PATH else "?"
    return f"{base_url.rstrip('/')}{LANDING_PATH}{sep}{q}"


def compose_message(row: dict, base_url: str) -> tuple[str, str]:
    """Returns (sms/whatsapp_text, email_subject+body). Personalized, no fabricated claims."""
    first = (row.get("decision_maker") or "").title()
    company = row.get("company") or row.get("id") or "your business"
    pain = (row.get("pain") or "").rstrip(".")
    land = landing_url(base_url, row.get("prospect_id") or company)
    wa = (
        f"Hi {first} — quick one. You're likely losing revenue to: {pain.lower()}. "
        f"We run a 72-hour audit that maps exactly where leads leak before they become "
        f"revenue (${OFFER['price_usd']} flat, fix-list included): {land}"
    )
    subject = f"{company}: where your lead spend leaks revenue (72h audit)"
    body = (
        f"Hi {first},\n\n"
        f"You don't know me yet — short and specific:\n\n"
        f"Your situation (public signal): {pain}.\n\n"
        f"Our {OFFER['promise']} Flat ${OFFER['price_usd']}, delivered in 72 hours, "
        f"no retainer required.\n\n"
        f"Details + checkout: {land}\n\n"
        f"— MBM Revenue Engineering\n"
    )
    return wa, f"{subject}\n{body}"


def build(base_url: str = DEFAULT_BASE_URL, limit: int | None = None) -> dict:
    if not QUEUE_JSON.exists():
        raise SystemExit(f"prospect queue missing: {QUEUE_JSON}")
    rows = json.loads(QUEUE_JSON.read_text(encoding="utf-8"))
    if limit:
        rows = rows[:limit]

    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()

    contacts_path = CAMPAIGN_DIR / "contact_log.jsonl"
    existing_ids = set(state.get("prospects", {}).keys())

    csv_rows = []
    playbook_lines = [
        "# whop_audit_day1 — Day-1 Playbook (HUMAN-RUN, nothing auto-sends)",
        "",
        f"Offer: **{OFFER['product']} ${OFFER['price_usd']} one-time** ({OFFER['product_id']})",
        f"Checkout: {CHECKOUT_URL}",
        f"Landing: {landing_url(base_url, 'CAMPAIGN')}",
        "",
        f"Rules: 1 touch per prospect today (max {MAX_TOUCHES_PER_PROSPECT} total). "
        "Mark each touch:",
        "`python MBM/Whop/whop_first_revenue_campaign.py mark <ID> --status contacted`",
        "",
        "Follow-up schedule (stop permanently after):",
        *[f"- D{f['day']}: {f['rule']} (cap {f['cap']})" for f in FOLLOW_UP_SCHEDULE],
        "",
    ]

    for r in rows:
        pid = "AUDIT-" + str(r.get("rank", "")).zfill(2)
        r["prospect_id"] = pid
        wa, mail = compose_message(r, base_url)
        phone_raw = (r.get("phone") or r.get("evidence", {}).get("phone") or "").strip()
        digits = "".join(c for c in phone_raw if c.isdigit())
        wa_link = f"https://wa.me/{digits}?text={urllib.parse.quote(wa)}" if digits else ""
        gmail_link = (
            "https://mail.google.com/mail/?view=cm&fs=1&su="
            + urllib.parse.quote(mail.split("\n")[0])
            + "&body="
            + urllib.parse.quote(mail)
        )
        st = state["prospects"].get(pid, {})
        status = st.get("status", "pending")

        csv_rows.append({
            "prospect_id": pid,
            "business": r.get("company") or r.get("id"),
            "decision_maker": r.get("decision_maker"),
            "role": r.get("role"),
            "phone": phone_raw,
            "source": "CMS_NPI_REGISTRY",
            "channel": r.get("recommended_channel") or "PHONE",
            "message_key": f"{pid}_v1",
            "timestamp": _now(),
            "status": status,
            "response": st.get("response", ""),
            "cta": CHECKOUT_URL,
            "tracked_landing_url": landing_url(base_url, pid),
            "checkout_started": "TRUE" if st.get("checkout_started_at") else "FALSE",
            "purchase": "TRUE" if st.get("purchased_at") else "FALSE",
        })

        playbook_lines += [
            f"## {pid} — {r.get('company')} ({r.get('decision_maker')}, {r.get('role')})",
            f"- Phone: `{phone_raw}` | Channel: {r.get('recommended_channel')} | Status: **{status.upper()}**",
            f"- Why now: {r.get('why_now')}",
            f"- [WhatsApp 1-click]({wa_link})" if wa_link else "- WhatsApp: n/a",
            f"- [Gmail 1-click]({gmail_link})",
            f"<details><summary>Message text</summary><br>{wa}</details>",
            "",
        ]

        if pid not in existing_ids:
            state["prospects"][pid] = {"status": "pending", "created_at": _now()}
            existing_ids.add(pid)

    fields = list(csv_rows[0].keys())
    with open(CAMPAIGN_DIR / "prospects.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    try:
        source_rel = str(QUEUE_JSON.relative_to(ROOT_DIR))
    except ValueError:
        source_rel = str(QUEUE_JSON)
    campaign = {**OFFER, "base_url": base_url, "prospects": len(csv_rows),
                "source_file": source_rel,
                "follow_up_schedule": FOLLOW_UP_SCHEDULE,
                "max_touches_per_prospect": MAX_TOUCHES_PER_PROSPECT,
                "generated_at": _now(), "send_policy": "HUMAN_APPROVED_ONLY_governor_L3"}
    _atomic_write(CAMPAIGN_DIR / "campaign.json", json.dumps(campaign, indent=2))
    _atomic_write(CAMPAIGN_DIR / "DAY1_PLAYBOOK.md", "\n".join(playbook_lines) + "\n")
    _save_state(state)

    if not contacts_path.exists():
        contacts_path.touch()

    print(json.dumps({"status": "success", "outputs": {"dir": str(CAMPAIGN_DIR),
                          "prospects": len(csv_rows)}, "errors": [],
                          "next_action": "open DAY1_PLAYBOOK.md; work top-down; mark() after each touch",
                          "owner": "human", "timestamp": _now()}, indent=2))
    return campaign


def mark(prospect_id: str, status: str, note: str = "") -> dict:
    if status not in STATUSES:
        raise SystemExit(f"invalid status '{status}'. Allowed: {STATUSES}")
    state = _load_state()
    p = state["prospects"].get(prospect_id)
    if not p:
        raise SystemExit(f"unknown prospect_id '{prospect_id}' — run build first")
    prev = p.get("status")
    p["status"] = status
    if note:
        p.setdefault("notes", []).append({"at": _now(), "text": note})
    if status == "contacted":
        p["contacted_at"] = _now()
        with open(CAMPAIGN_DIR / "contact_log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prospect_id": prospect_id, "at": _now(),
                                 "status_before": prev, "status_after": status}) + "\n")
    if status == "replied":
        p.setdefault("responded_at", _now())
    if status == "checkout_started":
        p["checkout_started_at"] = _now()
    if status == "purchased":
        p["purchased_at"] = _now()
    _save_state(state)
    print(json.dumps({"status": "success", "outputs": {"prospect_id": prospect_id,
                          "status": status}, "timestamp": _now()}, indent=2))
    return p


def diagnose(counts: dict, webhook_real_events: int) -> list[str]:
    problems = []
    if counts["generated"] == 0:
        problems.append("NO_CAMPAIGN: run build")
        return problems
    if counts["contacted"] == 0:
        problems.append("NO_TRAFFIC -> distribution problem: touches not made yet")
        return problems
    if counts["replied"] == 0:
        problems.append("TOUCHED_NO_REPLY -> positioning/message problem")
    if counts["replied"] > 0 and counts["checkout_started"] == 0:
        problems.append("REPLY_NO_CHECKOUT -> offer/landing problem")
    if counts["checkout_started"] > 0 and counts["purchased"] == 0:
        problems.append("CHECKOUT_NO_PURCHASE -> checkout/trust/pricing problem")
    if counts["purchased"] > 0 and webhook_real_events == 0:
        problems.append("PURCHASE_NO_WEBHOOK -> integration problem: register Whop webhook NOW")
    if counts["purchased"] > 0 and webhook_real_events > 0:
        problems.append("FUNNEL_HEALTHY_THROUGH_PURCHASE -> next: fulfillment + upsell")
    return problems


def funnel() -> dict:
    state = _load_state()
    counts = {k: 0 for k in STAGE_ORDER}
    for p in state["prospects"].values():
        s = p.get("status", "pending")
        if s == "opted_out":
            continue
        idx = STAGE_ORDER.index(s) if s in STAGE_ORDER else 0
        counts["generated"] += 1
        for stage in STAGE_ORDER[1: idx + 1]:
            counts[stage] += 1
    webhook_real = 0
    evlog = EVENTS_LOG
    if evlog.exists():
        for line in evlog.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event_name") == "purchase" and e.get("source") == "whop_webhook" \
                    and not str(e.get("event_id", "")).startswith("smoke_"):
                webhook_real += 1
    problems = diagnose(counts, webhook_real)
    out = {"status": "success", "inputs": {"campaign": OFFER["campaign"]},
           "outputs": {"stages": counts, "webhook_real_purchases": webhook_real,
                       "diagnosis": problems},
           "errors": [], "next_action": problems[0] if problems else "scale_touches",
           "owner": "system", "timestamp": _now()}
    print(json.dumps(out, indent=2))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--base-url", default=DEFAULT_BASE_URL)
    b.add_argument("--limit", type=int, default=None)
    m = sub.add_parser("mark")
    m.add_argument("prospect_id")
    m.add_argument("--status", required=True, choices=STATUSES)
    m.add_argument("--note", default="")
    sub.add_parser("funnel")
    args = ap.parse_args()
    if args.cmd == "build":
        build(args.base_url, args.limit)
    elif args.cmd == "mark":
        mark(args.prospect_id, args.status, args.note)
    elif args.cmd == "funnel":
        funnel()


if __name__ == "__main__":
    main()
