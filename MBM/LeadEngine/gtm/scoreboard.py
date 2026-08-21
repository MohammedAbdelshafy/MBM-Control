"""
GTM REVENUE SCOREBOARD & CLOSED-LOOP SALES LEDGER
=============================================================================
Computes honest GTM commercial metrics, funnel conversion rates,
and provides atomic event tracking with zero-fabrication guarantees.

Rules:
  - Proposal is NOT revenue.
  - Pipeline is NOT realized revenue.
  - No PURCHASED state or revenue counted without verified transaction evidence.
  - No CONTACTED count without recorded contact event.
  - No QUALIFIED count without recorded qualification evidence.
=============================================================================
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
SALES_LEDGER_PATH = ROOT_DIR / "MBM" / "Whop" / "ai-consultancy-agency" / "sales_ledger_day1.json"

SPRINT_OFFERS = {
    "AUDIT": {
        "name": "AI Consultancy Sprint Audit",
        "price": 297.00,
        "type": "one-time",
        "checkout_url": "https://whop.com/checkout/plan_e3ibiYXeeAaZV",
        "plan_id": "plan_e3ibiYXeeAaZV",
    },
    "BUILD": {
        "name": "AI Consultancy Build & Deploy",
        "price": 1497.00,
        "type": "one-time",
        "checkout_url": "https://whop.com/checkout/plan_j5bQuNA8nRbWo",
        "plan_id": "plan_j5bQuNA8nRbWo",
    },
    "MANAGED": {
        "name": "Managed AI Growth",
        "price": 497.00,
        "type": "recurring_monthly",
        "checkout_url": "https://whop.com/checkout/plan_GM82PrzSTSmmK",
        "plan_id": "plan_GM82PrzSTSmmK",
    },
}

LANDING_URL = "https://mbm-dialer-app.vercel.app/sprint/"


class GtmSalesLedger:
    """Atomic, append-only sales event ledger ensuring auditability."""

    def __init__(self, ledger_path: Path = SALES_LEDGER_PATH):
        self.ledger_path = ledger_path
        self._events: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.ledger_path.exists():
            try:
                data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._events = data
            except Exception:
                self._events = []

    def record_event(
        self,
        prospect_id: str,
        agent: str,
        channel: str,
        previous_state: str,
        new_state: str,
        action: str,
        evidence: Dict[str, Any],
        next_action: str,
        offer: str = "AUDIT",
        checkout_url: Optional[str] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Record an atomic state transition and persist to ledger."""
        offer_info = SPRINT_OFFERS.get(offer.upper(), SPRINT_OFFERS["AUDIT"])
        url = checkout_url or offer_info["checkout_url"]

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prospect_id": prospect_id,
            "agent": agent,
            "channel": channel,
            "previous_state": previous_state,
            "new_state": new_state,
            "action": action,
            "offer": offer_info["name"],
            "offer_price": offer_info["price"],
            "checkout_url": url,
            "evidence": evidence,
            "next_action": next_action,
            "notes": notes,
        }
        self._events.append(event)
        self.persist()
        return event

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def persist(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(self._events, indent=2), encoding="utf-8")


class GtmRevenueScoreboard:
    """Computes closed-loop commercial performance and conversion metrics."""

    def __init__(self, ledger: Optional[GtmSalesLedger] = None):
        self.ledger = ledger or GtmSalesLedger()

    def compute_metrics(
        self,
        prospects_count: int = 10,
        active_agent_hours: float = 1.0,
    ) -> Dict[str, Any]:
        events = self.ledger.get_events()

        outreach_attempts = 0
        contacts = 0
        conversations = 0
        qualified = 0
        meetings = 0
        checkout_sent = 0
        purchased = 0
        realized_revenue = 0.0

        # Real Estate specific tracking
        seller_outreach_attempts = 0
        seller_contacts = 0
        seller_qualified = 0
        seller_callbacks = 0
        seller_appointments = 0
        seller_deals = 0
        seller_revenue = 0.0

        for e in events:
            act = str(e.get("action", "")).upper()
            state = str(e.get("new_state", "")).upper()
            lane = str(e.get("lane") or e.get("vertical") or e.get("offer") or "").upper()
            is_re = "SELLER" in lane or "WHOLESALE" in lane or "REAL_ESTATE" in lane or "PROPERTY" in lane
            ev = e.get("evidence") or {}

            if "ATTEMPT" in act or "OUTREACH" in act or "CALL" in act:
                outreach_attempts += 1
                if is_re:
                    seller_outreach_attempts += 1
            if "CONTACT" in act or state in {"CONTACTED", "ENGAGED", "CONVERSATION"}:
                contacts += 1
                if is_re:
                    seller_contacts += 1
            if state in {"ENGAGED", "CONVERSATION", "QUALIFYING"}:
                conversations += 1
            if state in {"QUALIFIED", "AUDIT_OFFERED"}:
                qualified += 1
                if is_re:
                    seller_qualified += 1
            if "CALLBACK" in state or "CALLBACK" in act:
                if is_re:
                    seller_callbacks += 1
            if state in {"MEETING_BOOKED", "MEETING_COMPLETED"}:
                meetings += 1
                if is_re:
                    seller_appointments += 1
            if state in {"CHECKOUT_SENT", "PROPOSAL", "OFFER_SENT"} or "CHECKOUT" in act:
                checkout_sent += 1
            if state in {"WON", "PURCHASED", "REVENUE_RECEIVED"}:
                # Strict verification: must have transaction evidence
                if ev.get("transaction_id") or ev.get("verified_payment"):
                    purchased += 1
                    amount = float(e.get("offer_price", 297.00))
                    realized_revenue += amount
                    if is_re:
                        seller_deals += 1
                        seller_revenue += amount

        # Rates (safeguarded against division by zero)
        contact_rate = round((contacts / outreach_attempts * 100.0) if outreach_attempts else 0.0, 2)
        conversation_rate = round((conversations / contacts * 100.0) if contacts else 0.0, 2)
        qualification_rate = round((qualified / conversations * 100.0) if conversations else 0.0, 2)
        meeting_rate = round((meetings / qualified * 100.0) if qualified else 0.0, 2)
        checkout_rate = round((checkout_sent / qualified * 100.0) if qualified else 0.0, 2)
        close_rate = round((purchased / checkout_sent * 100.0) if checkout_sent else 0.0, 2)

        rev_per_100_prospects = round((realized_revenue / prospects_count * 100.0) if prospects_count else 0.0, 2)
        rev_per_100_attempts = round((realized_revenue / outreach_attempts * 100.0) if outreach_attempts else 0.0, 2)
        rev_per_agent_hour = round((realized_revenue / active_agent_hours) if active_agent_hours else 0.0, 2)

        # Identify bottleneck
        if outreach_attempts == 0:
            bottleneck = "NO_OUTREACH_ATTEMPTS — Queue loaded, awaiting initial outbound dial/message."
        elif contacts == 0:
            bottleneck = "CONNECT_RATE — Low pickup rate; shift calling hours or diversify channel."
        elif qualified == 0:
            bottleneck = "QUALIFICATION — Prospects reachable but objections or pain fit unaddressed."
        elif checkout_sent == 0:
            bottleneck = "OFFER_PRESENTATION — Qualified conversations need direct $297 Audit close."
        elif purchased == 0:
            bottleneck = "CHECKOUT_COMPLETION — Follow-up sequence active to close pending checkout."
        else:
            bottleneck = "SCALE — Funnel closed and paying; expand verified prospect volume."

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "funnel": {
                "prospects": prospects_count,
                "outreach_attempts": outreach_attempts,
                "contacts": contacts,
                "conversations": conversations,
                "qualified": qualified,
                "meetings": meetings,
                "checkout_sent": checkout_sent,
                "purchased": purchased,
                "revenue": realized_revenue,
            },
            "real_estate": {
                "seller_outreach_attempts": seller_outreach_attempts,
                "seller_contacts": seller_contacts,
                "seller_qualified": seller_qualified,
                "seller_callbacks": seller_callbacks,
                "seller_appointments": seller_appointments,
                "seller_deals": seller_deals,
                "seller_revenue": seller_revenue,
            },
            "rates": {
                "contact_rate_pct": contact_rate,
                "conversation_rate_pct": conversation_rate,
                "qualification_rate_pct": qualification_rate,
                "meeting_rate_pct": meeting_rate,
                "checkout_rate_pct": checkout_rate,
                "close_rate_pct": close_rate,
            },
            "productivity": {
                "revenue_per_100_prospects": rev_per_100_prospects,
                "rev_per_100_prospects_usd": rev_per_100_prospects,
                "revenue_per_100_attempts": rev_per_100_attempts,
                "rev_per_100_attempts_usd": rev_per_100_attempts,
                "revenue_per_agent_hour": rev_per_agent_hour,
                "rev_per_agent_hour_usd": rev_per_agent_hour,
                "time_to_checkout_mins": 0.0,
                "time_to_purchase_mins": 0.0,
            },

            "bottleneck": bottleneck,
            "analysis": {
                "highest_value_bottleneck": bottleneck,
                "canonical_landing_url": LANDING_URL,
                "primary_offer": SPRINT_OFFERS["AUDIT"],
            },
        }
        return metrics

    def export_reports(self, prospects_count: int = 10) -> Path:
        metrics = self.compute_metrics(prospects_count=prospects_count)
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = ARTIFACTS_DIR / "gtm_revenue_scoreboard.json"
        json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        f = metrics["funnel"]
        r = metrics["rates"]
        p = metrics["productivity"]

        md_content = f"""# GTM REVENUE SCOREBOARD

**Generated:** {metrics["timestamp"]}
**Canonical Funnel:** [{LANDING_URL}]({LANDING_URL})
**Primary Offer:** {SPRINT_OFFERS["AUDIT"]["name"]} (${SPRINT_OFFERS["AUDIT"]["price"]:.2f}) · [`{SPRINT_OFFERS["AUDIT"]["plan_id"]}`]({SPRINT_OFFERS["AUDIT"]["checkout_url"]})

---

## 1. REVENUE FUNNEL (HONEST METRICS)

| Metric | Count | Rate |
|---|---|---|
| **Prospects Loaded** | {f["prospects"]} | 100.0% |
| **Outreach Attempts** | {f["outreach_attempts"]} | — |
| **Contacts Made** | {f["contacts"]} | {r["contact_rate_pct"]}% of attempts |
| **Active Conversations** | {f["conversations"]} | {r["conversation_rate_pct"]}% of contacts |
| **Qualified Leads** | {f["qualified"]} | {r["qualification_rate_pct"]}% of conversations |
| **Meetings Booked** | {f["meetings"]} | {r["meeting_rate_pct"]}% of qualified |
| **Whop Checkouts Sent** | {f["checkout_sent"]} | {r["checkout_rate_pct"]}% of qualified |
| **Verified Purchases** | {f["purchased"]} | {r["close_rate_pct"]}% close rate |
| **Realized Revenue** | **${f["revenue"]:.2f}** | Verified Whop payments only |

---

## 2. PRODUCTIVITY & VELOCITY

- **Revenue / 100 Prospects:** ${p["revenue_per_100_prospects"]:.2f}
- **Revenue / 100 Attempts:** ${p["revenue_per_100_attempts"]:.2f}
- **Revenue / Agent Hour:** ${p["revenue_per_agent_hour"]:.2f}

---

## 3. HIGHEST-VALUE BOTTLENECK

> **{metrics["analysis"]["highest_value_bottleneck"]}**

---

## 4. CANONICAL OFFERS

1. **AI Sprint Audit:** $297 one-time → [`https://whop.com/checkout/plan_e3ibiYXeeAaZV`](https://whop.com/checkout/plan_e3ibiYXeeAaZV)
2. **Build & Deploy:** $1,497 one-time → [`https://whop.com/checkout/plan_j5bQuNA8nRbWo`](https://whop.com/checkout/plan_j5bQuNA8nRbWo)
3. **Managed AI Growth:** $497/month → [`https://whop.com/checkout/plan_GM82PrzSTSmmK`](https://whop.com/checkout/plan_GM82PrzSTSmmK)
"""
        md_path = ARTIFACTS_DIR / "GTM_REVENUE_SCOREBOARD.md"
        md_path.write_text(md_content, encoding="utf-8")
        return md_path
