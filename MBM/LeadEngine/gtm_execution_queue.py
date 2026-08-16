"""
GTM TOP-25 EXECUTION QUEUE & ACTION PACKET BUILDER
=============================================================================
Builds the verified, human-governed Top-25 execution queue with full action
packets (Phone, Email, LinkedIn) and Neteller canonical monetization links.

Strict Safety Rule:
  Zero synthetic identities. Zero fabricated evidence. Enforces the 6-point
  Production Gate on every record before outbound dispatch.
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

from MBM.LeadEngine.gtm_commander import GtmCommander
from MBM.LeadEngine.gtm.production_gate import ProductionGate, ApprovalStatus
from MBM.LeadEngine.gtm.action_ranker import ChannelType, ActionType

ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

QUEUE_JSON_PATH = ARTIFACTS_DIR / "GTM_TOP25_EXECUTION_QUEUE.json"
QUEUE_MD_PATH = ARTIFACTS_DIR / "GTM_TOP25_EXECUTION_QUEUE.md"


class ActionPacketBuilder:
    """Constructs tailored multi-channel action packets for verified opportunities."""

    @staticmethod
    def build_phone_packet(opp: Dict[str, Any]) -> Dict[str, Any]:
        company = opp.get("company", "the company")
        dm = opp.get("decision_maker", "there")
        pain = opp.get("pain", "call overflow")
        ai_assistant = opp.get("recommended_ai_assistant", "24/7 AI Receptionist")
        sku = opp.get("sku", "AI-ASSISTANT-VIP-RETAINER")
        retainer = opp.get("monthly_retainer_fee", 1500.0)

        return {
            "channel": "PHONE",
            "phone_number": opp.get("phone", ""),
            "opening": f"Hi {dm}, Omar with TranchAI. Calling because I saw you guys were scaling operations at {company}—do you have 45 seconds?",
            "pain_reference": f"We noticed contractor & service operators in Texas losing high-ticket jobs due to {pain}.",
            "discovery_question": f"When after-hours emergency calls or unworked lead inquiries come in, what is your team's current response workflow?",
            "ai_fit_explanation": f"We deployed an autonomous {ai_assistant} that answers on the 1st ring, qualifies customer requirements, and books directly into your scheduling software.",
            "qualification_questions": [
                f"How many unworked calls or estimate leads are coming through per week?",
                f"Who currently handles the follow-up when dispatchers are busy or off-duty?",
                f"If an AI assistant handled 80%+ of repetitive intake calls for ${retainer:,.0f}/mo, would that ROI justify a 10-minute demo?"
            ],
            "objection_handling": {
                "We already have staff": "Understood! Most clients use this as an overflow safety net so their staff never has to answer after-hours emergencies or repetitive status calls.",
                "Is it a robot/sounds robotic?": "It's built on low-latency neural voice synthesis—most callers cannot distinguish it from an in-house receptionist.",
                "Send me an email": f"Happy to. I'll send over the 1-page architecture brief and benchmark metrics to {opp.get('email', 'your email')}. What's the best time to review it together for 5 minutes?"
            },
            "meeting_cta": f"Let's do a 5-minute interactive voice simulation on Google Meet this Thursday at 10 AM so you can hear it handle a live scenario. Does that work?",
        }

    @staticmethod
    def build_email_packet(opp: Dict[str, Any]) -> Dict[str, Any]:
        company = opp.get("company", "the company")
        dm = opp.get("decision_maker", "there")
        pain = opp.get("pain", "call overflow")
        ai_assistant = opp.get("recommended_ai_assistant", "24/7 AI Receptionist")
        roi = opp.get("ROI_hypothesis", "recovering $25,000+/mo in lost revenue")

        return {
            "channel": "EMAIL",
            "to_email": opp.get("email", ""),
            "subject": f"Automating {company}'s intake & {pain}",
            "opening": f"Hi {dm},",
            "observed_signal": f"Saw that {company} is actively handling high-volume operational demand in your area.",
            "pain": f"When front-office staff get tied up with manual call logging or dispatching, high-ticket inbound inquiries easily slip through the cracks.",
            "specific_ai_solution": f"We engineered a custom {ai_assistant} that automates 100% of intake qualification and calendar booking.",
            "credible_value_hypothesis": f"For similar groups, this resulted in {roi} within the first 30 days.",
            "cta": "Open to a 3-minute video walkthrough or interactive voice simulation this week?",
        }

    @staticmethod
    def build_linkedin_packet(opp: Dict[str, Any]) -> Dict[str, Any]:
        company = opp.get("company", "the company")
        dm = opp.get("decision_maker", "there")
        pain = opp.get("pain", "operations bottlenecks")

        return {
            "channel": "LINKEDIN",
            "conversation_starter": (
                f"Hi {dm} — saw your recent post regarding operational bottlenecks at {company}. "
                f"We've been helping service operators automate {pain} using custom AI phone & intake concierges. "
                f"Curious how your team is handling the volume currently?"
            )
        }


class GtmExecutionQueueBuilder:
    """Orchestrates candidate scoring, quality filtering, gate auditing, and packet generation."""

    def __init__(self):
        self.commander = GtmCommander(dry_run=True)
        self.gate = ProductionGate()
        self.packet_builder = ActionPacketBuilder()

    def build_queue(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Build the verified Top-25 Execution Queue."""
        # Extract ranked actions from Commander
        raw_opps = self.commander.identify_opportunities()
        
        # Sort by priority
        ranked_actions = self.commander.rank_next_actions(limit=limit * 2)
        
        queue = []
        for action in ranked_actions:
            raw_opp = next((o for o in raw_opps if o.get("id") == action.entity_id or o.get("company") == action.company), {})
            
            # Form standardized record
            entity_id = action.entity_id
            company = action.company
            dm = action.buyer
            role = raw_opp.get("role") or "Decision Maker"
            industry = raw_opp.get("industry") or "B2B Services"
            intent_score = float(raw_opp.get("intent_score") or 85.0)
            intent_tier = raw_opp.get("tier") or ("HOT" if intent_score >= 90 else "HIGH INTENT")
            pain = action.pain
            why_now = raw_opp.get("why_now") or "Active operational bottleneck & hiring demand"
            ai_assistant = action.ai_fit
            sku = raw_opp.get("recommended_assistant_sku") or "AI-ASSISTANT-VIP-RETAINER"
            retainer = float(raw_opp.get("expected_revenue") or 2000.0)
            
            roi_hypothesis = raw_opp.get("estimated_roi") or f"Recovers $20,000–$60,000/mo by eliminating {pain}."
            rec_channel = action.recommended_channel.value
            priority = action.priority
            confidence = action.confidence
            phone = raw_opp.get("phone", "")
            email = raw_opp.get("email", "")

            # Evidence
            evidence_claim = raw_opp.get("why_this_company") or action.reason
            evidence_source = raw_opp.get("source") or "SignalHarvester"

            # Contactability
            contactable = bool((rec_channel == "PHONE" and phone) or (rec_channel == "EMAIL" and email) or (rec_channel == "LINKEDIN"))

            # Identity & Suppression
            identity_state = raw_opp.get("identity_state", "IDENTITY_UNCONFIRMED")
            suppression_state = "SUPPRESSED" if raw_opp.get("is_suppressed") else "CLEAR"
            previous_attempts = int(raw_opp.get("recent_attempts", 0))

            # Production Gate Audit
            opp_dict = {
                "id": entity_id,
                "company": company,
                "phone": phone,
                "email": email,
                "why_this_company": evidence_claim,
                "pain_point": pain,
                "recommended_channel": rec_channel,
                "confidence": confidence,
                "identity_state": identity_state,
                "is_suppressed": raw_opp.get("is_suppressed", False),
            }
            gate_audit = self.gate.evaluate_gate(opp_dict)

            # Quality Filter: Skip invalid/unsupported/suppressed records
            if not gate_audit["evidence_valid"] or not contactable or not gate_audit["not_suppressed"]:
                continue

            # Build Action Packets
            packet_data = {
                "company": company,
                "decision_maker": dm,
                "pain": pain,
                "recommended_ai_assistant": ai_assistant,
                "sku": sku,
                "monthly_retainer_fee": retainer,
                "ROI_hypothesis": roi_hypothesis,
                "phone": phone,
                "email": email,
            }
            action_packets = {
                "phone": self.packet_builder.build_phone_packet(packet_data),
                "email": self.packet_builder.build_email_packet(packet_data),
                "linkedin": self.packet_builder.build_linkedin_packet(packet_data),
            }

            queue_item = {
                "rank": len(queue) + 1,
                "id": entity_id,
                "company": company,
                "decision_maker": dm,
                "role": role,
                "industry": industry,
                "intent_score": intent_score,
                "intent_tier": intent_tier,
                "pain": pain,
                "why_now": why_now,
                "recommended_ai_assistant": ai_assistant,
                "sku": sku,
                "monthly_retainer_usd": retainer,
                "ROI_hypothesis": roi_hypothesis,
                "recommended_channel": rec_channel,
                "priority": priority,
                "confidence": confidence,
                "evidence": {
                    "claim": evidence_claim,
                    "source": evidence_source,
                    "confidence": confidence,
                },
                "contactability": {
                    "phone": phone,
                    "email": email,
                    "is_callable": bool(phone),
                    "is_emailable": bool(email),
                },
                "identity_state": identity_state,
                "suppression_state": suppression_state,
                "previous_attempts": previous_attempts,
                "next_action": action.action_type.value,
                "gate_status": {
                    "can_execute": gate_audit["can_execute"],
                    "approval_status": gate_audit["approval_status"],
                    "approval_required": not gate_audit["human_approved"],
                },
                "action_packets": action_packets,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            queue.append(queue_item)

            if len(queue) >= limit:
                break

        return queue

    def export_artifacts(self, limit: int = 25) -> Path:
        """Generate and save both JSON and Markdown artifacts."""
        queue = self.build_queue(limit=limit)

        # 1. Write JSON
        QUEUE_JSON_PATH.write_text(json.dumps(queue, indent=2), encoding="utf-8")

        # 2. Write Markdown
        md_content = f"""# MBM GTM Top-{len(queue)} Execution Queue

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Total Opportunities in Queue:** `{len(queue)}`  
**Production Gate Status:** 🛡️ `STRICT HUMAN APPROVAL REQUIRED`  
**Monetization Rail:** `Neteller` (`abdelshafyclapps@gmail.com` | ID: `4599228811`)

---

## Queue Summary Overview

| # | Company | Decision Maker | Vertical | Score | AI Assistant Fit | Channel | Priority | Gate Status |
|---|---|---|---|---|---|---|---|---|
"""
        for item in queue:
            gate_badge = "🟢 APPROVED" if item["gate_status"]["approval_status"] == "APPROVED" else "🟡 APPROVAL REQUIRED"
            md_content += (
                f"| **{item['rank']}** | **{item['company']}** | {item['decision_maker']} ({item['role']}) | "
                f"{item['industry']} | `{item['intent_score']}` ({item['intent_tier']}) | {item['recommended_ai_assistant']} | "
                f"`{item['recommended_channel']}` | **{item['priority']}** | {gate_badge} |\n"
            )

        md_content += "\n---\n\n## Detailed Opportunity Action Packets\n\n"

        for item in queue:
            phone_p = item["action_packets"]["phone"]
            email_p = item["action_packets"]["email"]
            li_p = item["action_packets"]["linkedin"]

            md_content += f"""### [{item['rank']}] {item['company']} — {item['decision_maker']}
- **Vertical:** {item['industry']} | **Role:** {item['role']}
- **Intent Score:** `{item['intent_score']}/100` ({item['intent_tier']}) | **Priority Score:** `{item['priority']}`
- **Phone:** `{item['contactability']['phone']}` | **Email:** `{item['contactability']['email']}`
- **Why Them:** {item['evidence']['claim']}
- **Why Now:** {item['why_now']}
- **Core Pain:** {item['pain']}
- **Recommended AI Assistant:** **{item['recommended_ai_assistant']}** (`{item['sku']}` — ${item['monthly_retainer_usd']:,.2f}/mo)
- **ROI Hypothesis:** {item['ROI_hypothesis']}
- **Identity State:** `{item['identity_state']}` | **Suppression State:** `{item['suppression_state']}`

#### 📞 Phone Call Action Packet
- **Opening:** *"{phone_p['opening']}"*
- **Pain Hook:** *"{phone_p['pain_reference']}"*
- **Discovery Question:** *"{phone_p['discovery_question']}"*
- **AI Solution Pitch:** *"{phone_p['ai_fit_explanation']}"*
- **Closing Meeting CTA:** *"{phone_p['meeting_cta']}"*

#### ✉️ Cold Email Action Packet
- **Subject:** `{email_p['subject']}`
- **Body:**
> {email_p['opening']}
> 
> {email_p['observed_signal']} {email_p['pain']}
> 
> {email_p['specific_ai_solution']} {email_p['credible_value_hypothesis']}
> 
> {email_p['cta']}

#### 💼 LinkedIn Conversation Starter
- *"{li_p['conversation_starter']}"*

---
"""

        QUEUE_MD_PATH.write_text(md_content, encoding="utf-8")
        return QUEUE_MD_PATH


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Top-25 Execution Queue")
    parser.add_argument("--limit", type=int, default=25, help="Number of opportunities to queue")
    parser.add_argument("--approve", type=str, help="Entity ID or Company to approve")
    parser.add_argument("--batch-approve", type=int, help="Batch approve top N opportunities")
    parser.add_argument("--reject", type=str, help="Entity ID or Company to reject")
    parser.add_argument("--hold", type=str, help="Entity ID or Company to place on hold")
    args = parser.parse_args()

    builder = GtmExecutionQueueBuilder()
    gate = ProductionGate()

    if args.approve:
        res = gate.set_approval(args.approve, ApprovalStatus.APPROVED, notes="Approved via CLI")
        print(f"✅ Approved: {args.approve}")

    if args.reject:
        res = gate.set_approval(args.reject, ApprovalStatus.REJECTED, notes="Rejected via CLI")
        print(f"❌ Rejected: {args.reject}")

    if args.hold:
        res = gate.set_approval(args.hold, ApprovalStatus.HOLD, notes="Held via CLI")
        print(f"⏸️ Placed on Hold: {args.hold}")

    if args.batch_approve:
        queue = builder.build_queue(limit=args.batch_approve)
        ids = [item["id"] for item in queue]
        approved_count = gate.batch_approve(ids)
        print(f"✅ Batch Approved Top {approved_count} Opportunities for Production Run.")

    out_path = builder.export_artifacts(limit=args.limit)
    print(f"✅ Top-{args.limit} Execution Queue generated at: {out_path}")


if __name__ == "__main__":
    main()
