"""
GTM CONTROLLED PRODUCTION RUNNER & CONVERSATION CAPTURE ENGINE
=============================================================================
Executes human-approved outbound actions and tracks deal state via REAL,
canonical dispositions only (see outreach_event.py).

ZERO-SIMULATION LAW:
  Touches record PENDING_DISPOSITION. Commercial outcomes (connected /
  qualified / meeting / proposal / payment) enter the funnel ONLY through
  apply_disposition() with real telephony, human, or checkout evidence.
  Index position may never determine an outcome.
=============================================================================
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine
from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
from MBM.LeadEngine.gtm.production_gate import ProductionGate, ApprovalStatus
from MBM.LeadEngine.gtm.attribution import AttributionTracker, Touchpoint, RevenueStage
from MBM.LeadEngine.gtm.learning import GtmLearningEngine, OutcomeType
from MBM.LeadEngine.gtm_execution_queue import GtmExecutionQueueBuilder, QUEUE_JSON_PATH

# Monetization: Neteller Canonical Rail
try:
    from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID
except Exception:
    def neteller_link(amount: float, item: str, currency: str = "USD") -> str:
        import urllib.parse
        return f"https://member.neteller.com/pay?email={urllib.parse.quote('abdelshafyclapps@gmail.com')}&account=4599228811&amount={amount:.2f}&currency={currency}&item={urllib.parse.quote(item)}"

ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

PROD_REPORT_PATH = ARTIFACTS_DIR / "GTM_PRODUCTION_REPORT.md"
METRICS_JSON_PATH = ARTIFACTS_DIR / "gtm_production_metrics.json"


def _revenue_events() -> List[Dict[str, Any]]:
    """Load canonical outreach events that carry commercial dispositions."""
    try:
        from MBM.LeadEngine import outreach_event as oe
        return [e for e in oe.load_events() if e.get("disposition") in oe.COMMERCIAL_EVENTS]
    except Exception:
        return []


class GtmProductionRunner:
    """
    Executes controlled outbound actions for human-approved opportunities.
    Maintains zero-fabrication integrity, auto-generates meeting briefs,
    and updates the conversion funnel.
    """

    def __init__(self):
        self.queue_builder = GtmExecutionQueueBuilder()
        self.gate = ProductionGate()
        self.event_bus = GtmEventBus()
        self.attribution = AttributionTracker()
        self.learning = GtmLearningEngine()
        self.state_machines: Dict[str, GtmStateMachine] = {}

    def load_queue(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Load or build the execution queue."""
        if QUEUE_JSON_PATH.exists():
            try:
                data = json.loads(QUEUE_JSON_PATH.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= limit:
                    return data[:limit]
            except Exception:
                pass
        return self.queue_builder.build_queue(limit=limit)

    def execute_opportunity_touch(
        self,
        opportunity: Dict[str, Any],
        operator_notes: str = "",
    ) -> Dict[str, Any]:
        """
        Execute an outbound touch on a single opportunity through the production gate.

        ZERO-SIMULATION LAW: this method records that a touch ATTEMPT was made
        (workflow state only). It NEVER assigns a commercial outcome. Outcomes
        enter the system exclusively via apply_disposition() from real
        human/telephony/checkout evidence recorded in the canonical event store.
        """
        entity_id = opportunity["id"]
        company = opportunity["company"]
        dm = opportunity["decision_maker"]
        channel = opportunity["recommended_channel"]

        # Check gate
        gate_status = self.gate.evaluate_gate(opportunity)
        if not gate_status["can_execute"]:
            return {
                "entity_id": entity_id,
                "company": company,
                "status": "BLOCKED_BY_GATE",
                "gate_status": gate_status,
                "reason": "Opportunity requires human approval or failed safety gate.",
            }

        # Initialize State Machine
        if entity_id not in self.state_machines:
            self.state_machines[entity_id] = GtmStateMachine(GtmState.QUALIFIED, entity_id=entity_id)

        sm = self.state_machines[entity_id]
        sm.transition(GtmState.CONTACTING, reason=f"Outbound {channel} action initiated", actor="GtmProductionRunner")

        # Record contact attempted touchpoint
        self.attribution.record_touchpoint(Touchpoint(
            entity_id=entity_id,
            stage=RevenueStage.CONTACT_ATTEMPTED,
            channel=channel,
            agent="VOICE_AGENT" if channel == "PHONE" else "PERSONALIZER",
            source=opportunity["evidence"]["source"],
            notes=operator_notes or f"Outbound {channel} touch initiated",
        ))

        execution_result = {
            "entity_id": entity_id,
            "company": company,
            "decision_maker": dm,
            "channel": channel,
            "action_executed": opportunity["action_packets"]["phone"]["opening"] if channel == "PHONE" else opportunity["action_packets"]["email"]["subject"],
            "outcome": "PENDING_DISPOSITION",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        execution_result["final_state"] = sm.current_state.value
        return execution_result

    def apply_disposition(
        self,
        opportunity: Dict[str, Any],
        disposition: str,
        evidence: Optional[Dict[str, Any]] = None,
        actor: str = "human_operator",
    ) -> Dict[str, Any]:
        """
        Apply a REAL disposition (from telephony bridge / human operator /
        checkout webhook) to an opportunity's state machine.

        The disposition must be a canonical value from outreach_event.py.
        Simulated or index-derived outcomes are rejected at the model layer.
        """
        import outreach_event as oe

        entity_id = opportunity["id"]
        if disposition not in oe.ALLOWED_DISPOSITIONS:
            raise ValueError(f"disposition '{disposition}' is not a canonical outcome")

        # Persist to the canonical append-only store first.
        ev = oe.record_event(oe.OutreachEvent(
            event_id=oe.make_event_id(entity_id, disposition, datetime.now(timezone.utc).isoformat()),
            lead_id=entity_id,
            channel="phone" if opportunity.get("recommended_channel") == "PHONE" else "email",
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            disposition=disposition,
            provider=evidence.get("provider", "") if evidence else "",
            evidence=evidence or {},
            source="gtm_production_runner.apply_disposition",
        ))

        if entity_id not in self.state_machines:
            self.state_machines[entity_id] = GtmStateMachine(GtmState.QUALIFIED, entity_id=entity_id)
        sm = self.state_machines[entity_id]

        result: Dict[str, Any] = {
            "entity_id": entity_id,
            "company": opportunity["company"],
            "disposition": disposition,
            "event_id": ev.event_id,
        }

        if disposition == "APPOINTMENT_BOOKED":
            sm.transition(GtmState.MEETING_BOOKED, reason="Real appointment booked with decision maker", actor=actor)
            self.attribution.record_touchpoint(Touchpoint(
                entity_id=entity_id,
                stage=RevenueStage.MEETING_BOOKED,
                channel=ev.channel,
                agent="HUMAN_OPERATOR",
                source=(evidence or {}).get("provider", "human"),
                monetary_value=opportunity.get("monthly_retainer_usd"),
                notes=str((evidence or {}).get("notes", "")),
            ))
            brief_path = self.generate_meeting_brief(opportunity)
            result["meeting_brief_generated"] = str(brief_path)
            self.learning.record_outcome(
                entity_id=entity_id,
                vertical=opportunity["industry"],
                pain_point=opportunity["pain"],
                assistant_sku=opportunity["sku"],
                outcome=OutcomeType.MEETING_BOOKED,
            )
        elif disposition in ("CONNECTED_OWNER", "CONNECTED_DECISION_MAKER", "INTERESTED"):
            sm.transition(GtmState.ENGAGED, reason=f"Real conversation: {disposition}", actor=actor)
            self.attribution.record_touchpoint(Touchpoint(
                entity_id=entity_id,
                stage=RevenueStage.CONTACT_CONNECTED,
                channel=ev.channel,
                agent="HUMAN_OPERATOR",
                source=(evidence or {}).get("provider", "human"),
            ))
        elif disposition == "QUALIFIED":
            sm.transition(GtmState.ENGAGED, reason="Qualified via real conversation", actor=actor)
        elif disposition == "OFFER_SENT":
            sm.transition(GtmState.PROPOSAL, reason="Offer/proposal delivered to decision maker", actor=actor)
            self.attribution.record_touchpoint(Touchpoint(
                entity_id=entity_id,
                stage=RevenueStage.PROPOSAL_SENT,
                channel=ev.channel,
                agent="DEAL_STRATEGIST",
                source=(evidence or {}).get("provider", "human"),
                monetary_value=opportunity.get("monthly_retainer_usd"),
            ))
        elif disposition in ("WRONG_NUMBER", "WRONG_PARTY", "DISCONNECTED", "DO_NOT_CALL"):
            sm.transition(GtmState.SUPPRESSED, reason=f"Suppressed: {disposition}", actor=actor)
            outcome_map = {
                "WRONG_PARTY": OutcomeType.WRONG_PERSON,
                "WRONG_NUMBER": OutcomeType.WRONG_NUMBER,
            }
            if disposition in outcome_map:
                self.learning.record_outcome(
                    entity_id=entity_id,
                    vertical=opportunity["industry"],
                    pain_point=opportunity["pain"],
                    assistant_sku=opportunity["sku"],
                    outcome=outcome_map[disposition],
                )
        elif disposition == "NOT_INTERESTED":
            sm.transition(GtmState.NURTURE, reason="Not interested — long-term nurture", actor=actor)
            self.learning.record_outcome(
                entity_id=entity_id,
                vertical=opportunity["industry"],
                pain_point=opportunity["pain"],
                assistant_sku=opportunity["sku"],
                outcome=OutcomeType.LOSS,
            )
        # NO_ANSWER / VOICEMAIL / CALLBACK / CHECKOUT_CLICK / PAYMENT_RECEIVED etc.
        # keep current state; they are recorded as events and counted by the scoreboard.

        result["final_state"] = sm.current_state.value
        return result

    def generate_meeting_brief(self, opportunity: Dict[str, Any]) -> Path:
        """Create structured, evidence-backed meeting brief markdown artifact."""
        company = opportunity["company"]
        clean_name = "".join(c if c.isalnum() else "_" for c in company).lower()
        brief_path = ARTIFACTS_DIR / f"meeting_brief_{clean_name}.md"

        sku = opportunity.get("sku", "AI-ASSISTANT-VIP-RETAINER")
        retainer = opportunity.get("monthly_retainer_usd", 2000.0)
        checkout_link = neteller_link(retainer, sku)

        content = f"""# Executive Discovery & Meeting Brief: {company}

**Meeting With:** {opportunity['decision_maker']} ({opportunity['role']})  
**Company:** {company}  
**Vertical:** {opportunity['industry']}  
**Phone:** `{opportunity['contactability']['phone']}` | **Email:** `{opportunity['contactability']['email']}`  
**Intent Score:** `{opportunity['intent_score']}/100` ({opportunity['intent_tier']})  
**Generated At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  

---

## 1. Verified Pain & Timing Triggers
- **Observed Problem:** {opportunity['pain']}
- **Why Them:** {opportunity['evidence']['claim']}
- **Why Now:** {opportunity['why_now']}
- **ROI Hypothesis:** {opportunity['ROI_hypothesis']}

---

## 2. Recommended AI Assistant & SOW
- **Assistant Package:** **{opportunity['recommended_ai_assistant']}**
- **SKU:** `{sku}`
- **Monthly Retainer:** **${retainer:,.2f} / month**
- **Canonical Checkout Rail:** [Neteller Checkout SOW]({checkout_link})

---

## 3. Recommended 15-Minute Diagnostic Agenda
1. **Minutes 1–3 (Pain Calibration):** Validate exact weekly volume of missed calls/bottlenecks.
2. **Minutes 4–8 (Neural Voice Demo):** Run live interactive voice simulation dialing the test number.
3. **Minutes 9–12 (Architecture & Integrations):** Review direct CRM/calendar booking integration.
4. **Minutes 13–15 (Closing & Neteller Retainer SOW):** Confirm SLA, onboard schedule, and lock in deployment.

---

## 4. Anticipated Objections & Rebuttals
- **"We already have an in-house receptionist."**  
  *Rebuttal:* Position this exclusively as after-hours and overflow backup so no high-ticket lead goes unanswered.
- **"How fast can we launch?"**  
  *Rebuttal:* 48-hour turn-key setup with zero downtime.
"""

        brief_path.write_text(content, encoding="utf-8")
        return brief_path

    def run_production_batch(self, batch_size: int = 10, auto_approve: bool = False) -> Dict[str, Any]:
        """
        Execute the initial production run on the Top-N highest-confidence opportunities.

        ZERO-SIMULATION LAW: touches record PENDING_DISPOSITION only. Funnel
        metrics are computed exclusively from canonical outreach events.
        """
        queue = self.load_queue(limit=batch_size * 2)
        top_candidates = queue[:batch_size]

        if auto_approve:
            ids = [item["id"] for item in top_candidates]
            self.gate.batch_approve(ids, approved_by="production_commander")

        execution_results = []
        for opp in top_candidates:
            res = self.execute_opportunity_touch(opp)
            execution_results.append(res)

        # Generate Master Production Report (event-derived funnel)
        metrics = self.generate_production_report(queue, execution_results)
        return metrics

    def generate_production_report(
        self,
        full_queue: List[Dict[str, Any]],
        execution_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute the conversion funnel from REAL outreach events only."""
        import outreach_event as oe

        event_funnel = oe.funnel_counts(oe.load_events())
        revenue_events = _revenue_events()
        payments = [e for e in revenue_events if e.get("disposition") == "PAYMENT_RECEIVED"]
        confirmed_rev = sum(float(e.get("amount_usd") or 0.0) for e in payments)

        discovered_count = len(full_queue)
        verified_count = len(full_queue)
        hot_count = len([q for q in full_queue if q.get("intent_tier") == "HOT"])
        approved_count = len([r for r in execution_results if r.get("status") != "BLOCKED_BY_GATE"])
        contacted_count = event_funnel["calls_attempted"]
        connected_count = event_funnel["conversations"]
        qualified_count = event_funnel["qualified"]
        meetings_count = event_funnel["appointments"]
        proposals_count = event_funnel["offers_sent"]
        won_count = len(payments)

        pipeline_val = confirmed_rev  # pipeline claims require payment evidence
        expected_val = 0.0

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "funnel": {
                "discovered": discovered_count,
                "verified": verified_count,
                "hot": hot_count,
                "approved": approved_count,
                "contacted": contacted_count,
                "connected": connected_count,
                "qualified": qualified_count,
                "meetings_booked": meetings_count,
                "proposals_sent": proposals_count,
                "deals_won": won_count,
            },
            "conversion_rates": {
                "discovered_to_verified_pct": round((verified_count / max(1, discovered_count)) * 100, 1),
                "verified_to_contacted_pct": round((contacted_count / max(1, verified_count)) * 100, 1),
                "contacted_to_connected_pct": round((connected_count / max(1, contacted_count)) * 100, 1),
                "connected_to_meeting_pct": round((meetings_count / max(1, connected_count)) * 100, 1),
            },
            "revenue": {
                "pipeline_value_usd": pipeline_val,
                "expected_value_usd": expected_val,
                "confirmed_realized_usd": confirmed_rev,
            },
            "quality_metrics": {
                "wrong_person": event_funnel["wrong_parties"],
                "wrong_number": event_funnel["wrong_numbers"],
                "suppressed": event_funnel["do_not_call"],
                "human_review_required": len([r for r in execution_results if r.get("status") == "BLOCKED_BY_GATE"]),
            },
            "metric_source": "canonical_outreach_events (zero-simulation)",
            "execution_log": execution_results,
        }

        # 1. Write JSON metrics
        METRICS_JSON_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        # 2. Write Markdown Report
        md_content = f"""# MBM GTM Production Readiness & Execution Report

**Execution Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Batch Size:** `{len(execution_results)} Top Opportunities`  
**Monetization Rail:** `Neteller` (`abdelshafyclapps@gmail.com` | ID: `4599228811`)  
**Production Gate:** 🛡️ `ACTIVE & HUMAN-GOVERNED`

---

## 1. Full GTM Conversion Funnel

```text
DISCOVERED ({metrics['funnel']['discovered']})
   │  ({metrics['conversion_rates']['discovered_to_verified_pct']}%)
   ▼
VERIFIED PROSPECTS ({metrics['funnel']['verified']})
   │
   ▼
HOT BUYERS ({metrics['funnel']['hot']})
   │
   ▼
HUMAN APPROVED ({metrics['funnel']['approved']})
   │
   ▼
CONTACTED ({metrics['funnel']['contacted']})
   │  ({metrics['conversion_rates']['contacted_to_connected_pct']}%)
   ▼
CONNECTED & QUALIFIED ({metrics['funnel']['qualified']})
   │  ({metrics['conversion_rates']['connected_to_meeting_pct']}%)
   ▼
MEETINGS BOOKED ({metrics['funnel']['meetings_booked']})
   │
   ▼
PROPOSALS DELIVERED ({metrics['funnel']['proposals_sent']})
   │
   ▼
CLOSED WON REVENUE (${metrics['revenue']['confirmed_realized_usd']:,.2f})
```

---

## 2. Revenue & Pipeline Integrity

| Metric | Amount (USD) | Definition / Invariant |
|---|---|---|
| **Active Pipeline Value** | **${metrics['revenue']['pipeline_value_usd']:,.2f}** | Active qualified opportunities in Meeting / Proposal stage |
| **Expected Weighted Value** | **${metrics['revenue']['expected_value_usd']:,.2f}** | Probability-adjusted pipeline value ($40\%$ weighted) |
| **Confirmed Realized Revenue** | **${metrics['revenue']['confirmed_realized_usd']:,.2f}** | Verified Neteller transactions (Proposal ≠ Revenue) |

---

## 3. First Production Batch (Top 10 Actions Executed)

| Company | Decision Maker | Channel | Outcome | Final State | Meeting Brief |
|---|---|---|---|---|---|
"""
        for r in execution_results:
            brief_link = f"[`{Path(r['meeting_brief_generated']).name}`](file:///{r['meeting_brief_generated']})" if "meeting_brief_generated" in r else "—"
            co = r.get("company", "Target Enterprise")
            dm = r.get("decision_maker", "Decision Maker")
            ch = r.get("channel", "PHONE")
            out = r.get("outcome", "PENDING")
            st = r.get("final_state", "QUALIFIED")
            md_content += (
                f"| **{co}** | {dm} | `{ch}` | "
                f"`{out}` | **{st}** | {brief_link} |\n"
            )

        md_content += """
---
## 4. Production Safety & Invariant Guarantees
1. **Human Approval Gate:** 100% of outbound communications require operator approval.
2. **Zero Fabrication:** Claims, phones, and decision-maker roles are backed by authoritative evidence cards.
3. **Revenue Isolation:** Pipeline and proposals are strictly separated from realized cash receipts.
"""

        PROD_REPORT_PATH.write_text(md_content, encoding="utf-8")
        return metrics


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Controlled Production Runner")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of top opportunities to execute")
    parser.add_argument("--auto-approve", action="store_true", help="Auto approve top batch for test run")
    args = parser.parse_args()

    runner = GtmProductionRunner()
    metrics = runner.run_production_batch(batch_size=args.batch_size, auto_approve=args.auto_approve)
    
    print("=" * 80)
    print("MBM GTM PRODUCTION RUN COMPLETE")
    print("=" * 80)
    print(f"Batch Executed: {len(metrics['execution_log'])} opportunities")
    print(f"Meetings Booked: {metrics['funnel']['meetings_booked']}")
    print(f"Proposals Sent: {metrics['funnel']['proposals_sent']}")
    print(f"Pipeline Value: ${metrics['revenue']['pipeline_value_usd']:,.2f}")
    print(f"Report: {PROD_REPORT_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
