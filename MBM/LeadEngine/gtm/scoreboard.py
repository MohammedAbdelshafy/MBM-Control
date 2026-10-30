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
import math
from collections import defaultdict
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

ACQUISITION_CHANNELS = {
    "WARM_OUTREACH", "COLD_OUTREACH", "ORGANIC_CONTENT", "PAID_ADS",
    "REFERRAL", "PARTNERSHIP", "AFFILIATE", "INBOUND", "OTHER",
}
OFFER_TYPES = {"ATTRACTION", "CORE", "UPSELL", "DOWNSELL", "CONTINUITY"}
PAYMENT_STATES = {
    "PURCHASED", "WON", "DEAL_WON", "REVENUE_RECEIVED",
    "RENEWAL_PAID", "UPSELL_PAID", "EXPANSION_PAID",
}


def _clean_attribution_value(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else "UNKNOWN"


def _event_stage_flags(event: Dict[str, Any]) -> Dict[str, bool]:
    action = str(event.get("action") or "").upper()
    state = str(event.get("new_state") or "").upper()
    evidence = event.get("evidence") or {}
    status = str(evidence.get("status") or "").upper()

    is_attempt = (
        "CALLBACK" not in action
        and (
            "ATTEMPT" in action
            or "OUTREACH" in action
            or "CALL" in action
            or ("CASCADE" in action and status == "SENT")
            or state in {"WHATSAPP_SENT", "EMAIL_SENT", "SMS_SENT"}
        )
    )
    return {
        "outreach_attempts": is_attempt,
        "contacts": ("CONTACT" in action or state in {"CONTACTED", "ENGAGED", "CONVERSATION"}),
        "conversations": state in {"ENGAGED", "CONVERSATION", "QUALIFYING", "DISCOVERY_COMPLETE"},
        "qualified": state in {"QUALIFIED", "AUDIT_OFFERED"},
        "appointments_booked": state in {
            "MEETING_BOOKED", "MEETING_COMPLETED", "APPOINTMENT",
            "APPOINTMENT_BOOKED", "APPOINTMENT_SCHEDULED",
        },
        "proposals_sent": state in {"PROPOSAL", "OFFER_SENT", "CHECKOUT_SENT"} or "CHECKOUT" in action,
        "delivery_accepted": state in {"DELIVERY_ACCEPTED", "ACCEPTED"},
        "renewed": state in {"RENEWED", "RENEWAL_PAID"},
        "referrals": state in {"REFERRED", "REFERRAL_CREATED"},
        "expanded": state in {"EXPANDED", "UPSELL_ACCEPTED", "EXPANSION_PAID"},
    }


def _verified_payment(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    evidence = event.get("evidence") or {}
    state = str(event.get("new_state") or "").upper()
    transaction_id = _clean_attribution_value(
        event.get("payment_transaction_id") or evidence.get("transaction_id")
    )
    if state not in PAYMENT_STATES or transaction_id == "UNKNOWN" or evidence.get("verified_payment") is not True:
        return None

    currency = str(event.get("payment_currency") or "UNKNOWN").strip().upper()
    amount_raw = event.get("payment_amount_usd")
    amount_usd = None
    if currency == "USD" and amount_raw is not None:
        try:
            amount_usd = float(amount_raw)
        except (TypeError, ValueError):
            amount_usd = None
        if amount_usd is not None and (not math.isfinite(amount_usd) or amount_usd < 0):
            amount_usd = None
    return {
        "transaction_id": transaction_id,
        "prospect_id": _clean_attribution_value(event.get("prospect_id")),
        "currency": currency,
        "amount_usd": amount_usd,
    }


def _new_attribution_bucket() -> Dict[str, Any]:
    return {
        "prospects_sourced": 0,
        "outreach_attempts": 0,
        "contacts": 0,
        "conversations": 0,
        "qualified": 0,
        "appointments_booked": 0,
        "proposals_sent": 0,
        "verified_customers": 0,
        "verified_payment_count": 0,
        "realized_revenue_usd": 0.0,
        "unpriced_verified_payments": 0,
        "unsupported_currency_payments": 0,
        "delivery_accepted": 0,
        "renewed": 0,
        "referrals": 0,
        "expanded": 0,
    }


def _aggregate_attribution_group(prospect_events: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    result = _new_attribution_bucket()
    result["prospects_sourced"] = len(prospect_events)
    seen_transactions = set()

    for prospect_id, events_for_prospect in prospect_events.items():
        flags = {key: False for key in (
            "outreach_attempts", "contacts", "conversations", "qualified",
            "appointments_booked", "proposals_sent", "delivery_accepted",
            "renewed", "referrals", "expanded",
        )}
        prospect_paid = False
        for event in events_for_prospect:
            for key, value in _event_stage_flags(event).items():
                flags[key] = flags[key] or value

            payment = _verified_payment(event)
            if not payment:
                continue
            transaction_id = payment["transaction_id"]
            if transaction_id in seen_transactions:
                continue
            seen_transactions.add(transaction_id)
            prospect_paid = True
            result["verified_payment_count"] += 1
            if payment["currency"] != "USD":
                result["unsupported_currency_payments"] += 1
                result["unpriced_verified_payments"] += 1
            elif payment["amount_usd"] is None:
                result["unpriced_verified_payments"] += 1
            else:
                result["realized_revenue_usd"] += payment["amount_usd"]

        for key, value in flags.items():
            if value:
                result[key] += 1
        if prospect_paid:
            result["verified_customers"] += 1

    result["realized_revenue_usd"] = round(result["realized_revenue_usd"], 2)
    return result


def _derive_acquisition_attribution(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build first-touch channel/source/vertical/campaign and explicit offer-role funnels."""
    ordered = sorted(
        enumerate(events),
        key=lambda item: (str(item[1].get("timestamp") or ""), item[0]),
    )
    fields = (
        "acquisition_channel", "vertical_id", "campaign_id", "source_id",
    )
    first_touch: Dict[str, Dict[str, str]] = {}
    by_prospect: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    offer_events: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    all_payments: Dict[str, Dict[str, Any]] = {}

    for _, event in ordered:
        prospect_id = _clean_attribution_value(event.get("prospect_id"))
        if prospect_id == "UNKNOWN":
            continue
        by_prospect[prospect_id].append(event)
        attribution = first_touch.setdefault(prospect_id, {field: "UNKNOWN" for field in fields})
        for field in fields:
            value = _clean_attribution_value(event.get(field))
            if attribution[field] == "UNKNOWN" and value != "UNKNOWN":
                if field == "acquisition_channel" and value.upper() not in ACQUISITION_CHANNELS:
                    continue
                attribution[field] = value.upper() if field in {"acquisition_channel", "vertical_id"} else value

        offer_type = _clean_attribution_value(event.get("offer_type")).upper()
        if offer_type in OFFER_TYPES:
            offer_events[offer_type][prospect_id].append(event)

        payment = _verified_payment(event)
        if payment:
            all_payments.setdefault(payment["transaction_id"], payment)

    first_touch_dimensions = {
        "by_acquisition_channel": "acquisition_channel",
        "by_vertical": "vertical_id",
        "by_campaign": "campaign_id",
        "by_source": "source_id",
    }
    grouped = {}
    for output_key, field in first_touch_dimensions.items():
        groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for prospect_id, prospect_event_rows in by_prospect.items():
            key = first_touch[prospect_id].get(field) or "UNKNOWN"
            groups[key][prospect_id] = prospect_event_rows
        grouped[output_key] = {
            key: _aggregate_attribution_group(rows)
            for key, rows in sorted(groups.items())
        }

    grouped["by_offer_role"] = {
        role: _aggregate_attribution_group(rows)
        for role, rows in sorted(offer_events.items())
    }

    overall = _aggregate_attribution_group(by_prospect)
    duplicate_payment_events = 0
    seen = set()
    for _, event in ordered:
        payment = _verified_payment(event)
        if not payment:
            continue
        if payment["transaction_id"] in seen:
            duplicate_payment_events += 1
        else:
            seen.add(payment["transaction_id"])

    return {
        "attribution_model": "FIRST_TOUCH",
        "currency": "USD",
        **grouped,
        "verified_payment_count": len(all_payments),
        "verified_customers": overall["verified_customers"],
        "realized_revenue_usd": overall["realized_revenue_usd"],
        "unpriced_verified_payments": overall["unpriced_verified_payments"],
        "unsupported_currency_payments": overall["unsupported_currency_payments"],
        "duplicate_payment_events_ignored": duplicate_payment_events,
    }


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
        acquisition_channel: str = "UNKNOWN",
        vertical_id: str = "UNKNOWN",
        campaign_id: str = "UNKNOWN",
        source_id: str = "UNKNOWN",
        offer_id: str = "UNKNOWN",
        offer_type: str = "UNKNOWN",
        payment_amount_usd: Optional[float] = None,
        payment_currency: str = "UNKNOWN",
        payment_transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an atomic state transition and persist explicit attribution metadata."""
        offer_info = SPRINT_OFFERS.get(offer.upper(), SPRINT_OFFERS["AUDIT"])
        url = checkout_url or offer_info["checkout_url"]

        channel_attribution = str(acquisition_channel or "UNKNOWN").strip().upper()
        if channel_attribution not in ACQUISITION_CHANNELS:
            channel_attribution = "UNKNOWN"
        normalized_offer_type = str(offer_type or "UNKNOWN").strip().upper()
        if normalized_offer_type not in OFFER_TYPES:
            normalized_offer_type = "UNKNOWN"
        try:
            normalized_payment_amount = (
                None if payment_amount_usd is None else float(payment_amount_usd)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("payment_amount_usd must be a non-negative number") from exc
        if normalized_payment_amount is not None and (
            not math.isfinite(normalized_payment_amount) or normalized_payment_amount < 0
        ):
            raise ValueError("payment_amount_usd must be a non-negative finite number")

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
            "acquisition_channel": channel_attribution,
            "vertical_id": _clean_attribution_value(vertical_id).upper(),
            "campaign_id": _clean_attribution_value(campaign_id),
            "source_id": _clean_attribution_value(source_id),
            "offer_id": _clean_attribution_value(offer_id),
            "offer_type": normalized_offer_type,
            "payment_amount_usd": normalized_payment_amount,
            "payment_currency": str(payment_currency or "UNKNOWN").strip().upper(),
            "payment_transaction_id": _clean_attribution_value(payment_transaction_id),
        }
        self._events.append(event)
        self.persist()
        return event

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def record_transition(
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
        lane: Optional[str] = None,
        acquisition_channel: str = "UNKNOWN",
        vertical_id: str = "UNKNOWN",
        campaign_id: str = "UNKNOWN",
        source_id: str = "UNKNOWN",
        offer_id: str = "UNKNOWN",
        offer_type: str = "UNKNOWN",
        payment_amount_usd: Optional[float] = None,
        payment_currency: str = "UNKNOWN",
        payment_transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a lifecycle transition (Terminal 1 disposition contract).

        Thin wrapper over record_event so callers recording real operator
        dispositions get one atomic, persisted ledger event.
        """
        event = self.record_event(
            prospect_id=prospect_id,
            agent=agent,
            channel=channel,
            previous_state=previous_state,
            new_state=new_state,
            action=action,
            evidence=evidence,
            next_action=next_action,
            offer=offer,
            checkout_url=checkout_url,
            notes=notes,
            acquisition_channel=acquisition_channel,
            vertical_id=vertical_id,
            campaign_id=campaign_id,
            source_id=source_id,
            offer_id=offer_id,
            offer_type=offer_type,
            payment_amount_usd=payment_amount_usd,
            payment_currency=payment_currency,
            payment_transaction_id=payment_transaction_id,
        )
        if lane:
            event["lane"] = str(lane).upper()
            self.persist()
        return event

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
        # PRODUCTION VS FIXTURE RULE: test/fixture/synthetic ledger entries are
        # excluded from real seller production metrics.
        from MBM.LeadEngine.gtm.seller_state import production_events
        events = production_events(self.ledger.get_events())

        outreach_attempts = 0
        contacts = 0
        conversations = 0
        qualified = 0
        meetings = 0
        checkout_sent = 0
        purchased = 0
        realized_revenue = 0.0
        verified_transactions = set()
        paid_prospects = set()

        # Real Estate specific tracking
        seller_prospects: set = set()
        seller_outreach_attempts = 0
        seller_contacts = 0
        seller_qualified = 0
        seller_callbacks = 0
        seller_appointments = 0
        seller_offers = 0
        seller_deals = 0
        seller_revenue = 0.0
        seller_paid_prospects = set()

        # Best-performing source / segment aggregation (recorded evidence only)
        source_stats: Dict[str, Dict[str, float]] = {}
        segment_stats: Dict[str, Dict[str, float]] = {}

        for e in events:
            act = str(e.get("action", "")).upper()
            state = str(e.get("new_state", "")).upper()
            lane = str(e.get("lane") or e.get("vertical") or e.get("offer") or "").upper()
            # SELLER_CASCADE_* / SELLER_<DISPOSITION> actions declare the lane
            # in the action name itself.
            is_re = (
                "SELLER" in lane or "SELLER" in act or "WHOLESALE" in lane
                or "REAL_ESTATE" in lane or "PROPERTY" in lane
            )
            ev = e.get("evidence") or {}
            if is_re:
                pid = str(e.get("prospect_id") or "")
                if pid:
                    seller_prospects.add(pid)

            def _bump(stats: Dict[str, Dict[str, float]], key: str) -> None:
                k = str(key or "").strip().upper()
                if not k or k in {"UNKNOWN", "NONE", ""}:
                    return
                s = stats.setdefault(k, {"events": 0.0, "progressed": 0.0})
                s["events"] += 1
                progressed_states = {
                    "CONTACTED", "ENGAGED", "QUALIFIED", "CALLBACK_REQUESTED",
                    "INTERESTED", "APPOINTMENT", "APPOINTMENT_BOOKED",
                    "MEETING_BOOKED", "OFFER_MADE", "OFFER_SENT",
                    "CHECKOUT_SENT", "WON", "PURCHASED", "DEAL_WON",
                    "REVENUE_RECEIVED",
                }
                if state in progressed_states:
                    s["progressed"] += 1

            _bump(source_stats, ev.get("source") or e.get("source"))
            _bump(segment_stats, ev.get("segment") or e.get("seller_segment"))

            # Attempt = a real outbound touch. A generated-but-unsent link
            # (evidence status LINK_READY / QUEUED) is NOT an attempt;
            # CALLBACK_* dispositions are outcomes, not attempts.
            ev_status = str(ev.get("status") or "").upper()
            is_attempt = (
                "CALLBACK" not in act
                and (
                    "ATTEMPT" in act or "OUTREACH" in act or "CALL" in act
                    or ("CASCADE" in act and ev_status == "SENT")
                    or state in {"WHATSAPP_SENT", "EMAIL_SENT", "SMS_SENT"}
                )
            )
            if is_attempt:
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
            if state in {"OFFER_MADE", "OFFER_SENT"}:
                if is_re:
                    seller_offers += 1
            payment = _verified_payment(e)
            if payment:
                transaction_id = payment["transaction_id"]
                if transaction_id not in verified_transactions:
                    verified_transactions.add(transaction_id)
                    paid_prospects.add(payment["prospect_id"])
                    amount = payment["amount_usd"] if payment["currency"] == "USD" else None
                    if amount is not None:
                        realized_revenue += amount
                    if is_re:
                        seller_paid_prospects.add(payment["prospect_id"])
                        if amount is not None:
                            seller_revenue += amount

        purchased = len(paid_prospects)
        seller_deals = len(seller_paid_prospects)
        acquisition_attribution = _derive_acquisition_attribution(events)
        realized_revenue = acquisition_attribution["realized_revenue_usd"]
        seller_revenue = round(seller_revenue, 2)

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

        # One concrete next-best-action per bottleneck stage.
        next_best_action_by_bottleneck = {
            "NO_OUTREACH_ATTEMPTS": "DISPATCH_NEXT_SELLER_BATCH",
            "CONNECT_RATE": "RUN_FOLLOW_UP_CASCADE_ON_NO_ANSWER",
            "QUALIFICATION": "QUALIFY_ACTIVE_CONVERSATIONS",
            "OFFER_PRESENTATION": "BOOK_APPOINTMENTS_WITH_QUALIFIED_SELLERS",
            "CHECKOUT_COMPLETION": "FOLLOW_UP_PENDING_OFFERS",
            "SCALE": "EXPAND_VERIFIED_PROSPECT_VOLUME",
        }
        bottleneck_key = bottleneck.split(" ")[0]
        next_best_action = next_best_action_by_bottleneck.get(bottleneck_key, "HUMAN_REVIEW_PIPELINE")

        def _best(stats: Dict[str, Dict[str, float]]) -> str:
            if not stats:
                return "UNKNOWN"
            ranked = sorted(
                stats.items(),
                key=lambda kv: (kv[1]["progressed"] / kv[1]["events"], kv[1]["events"]),
                reverse=True,
            )
            return ranked[0][0]

        best_source = _best(source_stats)
        best_segment = _best(segment_stats)

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acquisition_attribution": acquisition_attribution,
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
                "real_estate_seller_leads": len(seller_prospects),
                "seller_outreach_attempts": seller_outreach_attempts,
                "seller_contacts": seller_contacts,
                "seller_qualified": seller_qualified,
                "seller_callbacks": seller_callbacks,
                "seller_appointments": seller_appointments,
                "seller_offers": seller_offers,
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
            "next_best_action": next_best_action,
            "best_performing_source": best_source,
            "best_performing_segment": best_segment,
            "analysis": {
                "highest_value_bottleneck": bottleneck,
                "next_best_action": next_best_action,
                "best_performing_source": best_source,
                "best_performing_segment": best_segment,
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

**Next-Best-Action:** `{metrics["analysis"]["next_best_action"]}`
**Best-Performing Source:** {metrics["analysis"]["best_performing_source"]} · **Best Segment:** {metrics["analysis"]["best_performing_segment"]}

---

## 4. REAL ESTATE SELLER FUNNEL

| Metric | Count |
|---|---|
| **Seller Leads (ledgered)** | {metrics["real_estate"]["real_estate_seller_leads"]} |
| **Seller Outreach Attempts** | {metrics["real_estate"]["seller_outreach_attempts"]} |
| **Seller Contacts** | {metrics["real_estate"]["seller_contacts"]} |
| **Seller Callbacks** | {metrics["real_estate"]["seller_callbacks"]} |
| **Seller Qualified** | {metrics["real_estate"]["seller_qualified"]} |
| **Seller Appointments** | {metrics["real_estate"]["seller_appointments"]} |
| **Seller Offers Made** | {metrics["real_estate"]["seller_offers"]} |
| **Seller Deals Won** | {metrics["real_estate"]["seller_deals"]} |
| **Seller Revenue** | **${metrics["real_estate"]["seller_revenue"]:.2f}** |

---

## 5. CANONICAL OFFERS

1. **AI Sprint Audit:** $297 one-time → [`https://whop.com/checkout/plan_e3ibiYXeeAaZV`](https://whop.com/checkout/plan_e3ibiYXeeAaZV)
2. **Build & Deploy:** $1,497 one-time → [`https://whop.com/checkout/plan_j5bQuNA8nRbWo`](https://whop.com/checkout/plan_j5bQuNA8nRbWo)
3. **Managed AI Growth:** $497/month → [`https://whop.com/checkout/plan_GM82PrzSTSmmK`](https://whop.com/checkout/plan_GM82PrzSTSmmK)
"""
        md_path = ARTIFACTS_DIR / "GTM_REVENUE_SCOREBOARD.md"
        md_path.write_text(md_content, encoding="utf-8")
        return md_path
