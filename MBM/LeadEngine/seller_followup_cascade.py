"""
MBM REAL ESTATE SELLER FOLLOW-UP CASCADE & MULTI-CHANNEL DISPATCH ENGINE
=============================================================================
Autonomous, idempotent follow-up cascade for verified Real Estate Sellers.

Channel Strategy:
  1. PRIMARY: WhatsApp (Direct 1-click bridge / automated API where available)
  2. FALLBACK: Email (ONLY when a verified email exists - zero fabrication)
  3. SECONDARY: Phone / Callback Task (when WhatsApp/Email cannot produce engagement)

Cadence:
  - DAY 0: Initial property acquisition outreach (DAY_0_INITIAL)
  - DAY 1: Follow-up 1 if no response (DAY_1_FOLLOWUP_1)
  - DAY 3: Second follow-up with offer framing (DAY_3_FOLLOWUP_2)
  - DAY 5: Final short check-in (DAY_5_FINAL_FOLLOWUP)
  - DAY 7+: Move to NURTURE / PHONE_CALLBACK

State Machine:
  QUEUED -> WHATSAPP_READY -> WHATSAPP_SENT -> WAITING_RESPONSE
  -> WHATSAPP_FOLLOWUP_DUE -> EMAIL_FALLBACK_ELIGIBLE -> EMAIL_SENT
  -> CONTACTED -> QUALIFIED -> APPOINTMENT -> DEAL
  (or DNC / NOT_INTERESTED / NURTURE)

Idempotency:
  - Tracks (lead_id, stage, channel) to strictly prevent duplicate outreach.
=============================================================================
"""

import os
import sys
import json
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter
from MBM.LeadEngine.dialer_priority_engine import (
    refresh_dialer_priority_queue,
    is_lead_suppressed,
    is_real_estate_seller,
    has_verified_owner_and_phone,
    _digits,
)
from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard
from MBM.LeadEngine.gtm.gmail_dispatcher import GmailDispatchAdapter

DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CASCADE_LOG_PATH = ROOT_DIR / "MBM" / "Artifacts" / "seller_cascade_history.json"
CASCADE_STATUS_DOC = ROOT_DIR / "MBM" / "Artifacts" / "SELLER_CASCADE_STATUS.md"

# Follow-up window intervals in hours
CADENCE_HOURS = {
    "DAY_0_INITIAL": 0,
    "DAY_1_FOLLOWUP_1": 24,
    "DAY_3_FOLLOWUP_2": 72,
    "DAY_5_FINAL_FOLLOWUP": 120,
}

CADENCE_STAGES = ["DAY_0_INITIAL", "DAY_1_FOLLOWUP_1", "DAY_3_FOLLOWUP_2", "DAY_5_FINAL_FOLLOWUP"]


def get_seller_templates(owner_name: str, property_address: str) -> Dict[str, Dict[str, str]]:
    """Returns multi-stage message copy tailored for real estate property sellers."""
    first_name = owner_name.split()[0] if owner_name else "there"
    prop = property_address or "your Texas property"

    return {
        "DAY_0_INITIAL": {
            "whatsapp": (
                f"Hi {first_name} -- reaching out regarding {prop} in TX. "
                f"We are actively acquiring properties in your area for direct portfolio investment. "
                f"If you received a fair, all-cash, as-is offer with zero closing costs, would you consider an offer? "
                f"Do you have 2 minutes to discuss?"
            ),
            "email_subject": f"Question regarding {prop}",
            "email_body": (
                f"Hi {first_name},\n\n"
                f"I'm reaching out regarding {prop} in Texas. Are you still the owner of this property?\n\n"
                f"We are actively acquiring residential and commercial assets in your area for direct portfolio investment. "
                f"If you would be open to a fair, all-cash, as-is offer with zero closing costs and flexible closing date, please let me know.\n\n"
                f"Best regards,\nMohammed Abdelshafy\nMBM Real Estate Acquisitions"
            ),
        },
        "DAY_1_FOLLOWUP_1": {
            "whatsapp": (
                f"Hi {first_name}, just following up on {prop}. "
                f"We can purchase in as-is condition with no repairs or fees needed on your end. "
                f"Would an all-cash offer be helpful for your timeline?"
            ),
            "email_subject": f"Follow-up: Cash offer review for {prop}",
            "email_body": (
                f"Hi {first_name},\n\n"
                f"Following up briefly regarding {prop}. "
                f"We can purchase in 100% as-is condition, covering all closing fees with no realtor commissions.\n\n"
                f"Would you be open to reviewing a preliminary offer this week?\n\n"
                f"Best regards,\nMohammed Abdelshafy"
            ),
        },
        "DAY_3_FOLLOWUP_2": {
            "whatsapp": (
                f"Hi {first_name} -- we are finalizing our Texas property acquisition budget this week. "
                f"Are you open to discussing an offer on {prop}, or should I check back with you next quarter?"
            ),
            "email_subject": f"Finalizing Texas acquisitions - {prop}",
            "email_body": (
                f"Hi {first_name},\n\n"
                f"We are finalizing our acquisition allocations for Texas properties this week. "
                f"Before moving to the next parcel, I wanted to see if you have any interest in selling {prop}.\n\n"
                f"Let me know either way!\n\n"
                f"Best,\nMohammed Abdelshafy"
            ),
        },
        "DAY_5_FINAL_FOLLOWUP": {
            "whatsapp": (
                f"Hi {first_name}, last check-in regarding {prop}. "
                f"If now isn't the right time to sell, no problem at all. Feel free to keep my contact for the future!"
            ),
            "email_subject": f"Closing inquiry for {prop}",
            "email_body": (
                f"Hi {first_name},\n\n"
                f"Last check-in regarding {prop}. If you're not interested in selling at this time, I'll close out my inquiry. "
                f"Feel free to reach out anytime if your plans change.\n\n"
                f"Best regards,\nMohammed Abdelshafy"
            ),
        },
    }



class SellerFollowupCascade:
    """
    Manages the multi-channel state machine and next-action determination
    for Real Estate Seller leads.
    """

    def __init__(self, db_path: Path = DIALER_DB_PATH, log_path: Path = CASCADE_LOG_PATH):
        self.db_path = db_path
        self.log_path = log_path
        self.writer = DialerSingleWriter(db_path=self.db_path)
        self.ledger = GtmSalesLedger()
        self.gmail = GmailDispatchAdapter()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        try:
            return json.loads(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_history(self, history: List[Dict[str, Any]]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def get_lead_history(self, lead_id: str) -> List[Dict[str, Any]]:
        history = self._load_history()
        return [h for h in history if str(h.get("lead_id")) == str(lead_id)]

    def determine_next_action(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the exact, single next action for a given seller lead based on
        channel availability, verified evidence, timestamps, and previous attempts.
        """
        lead_id = lead.get("id")
        if is_lead_suppressed(lead):
            return {
                "lead_id": lead_id,
                "status": "SUPPRESSED_DNC",
                "next_action": "DNC",
                "channel": "NONE",
                "reason": "Lead is marked DNC or Suppressed",
                "is_actionable": False,
            }

        if not is_real_estate_seller(lead) or not has_verified_owner_and_phone(lead):
            return {
                "lead_id": lead_id,
                "status": "UNQUALIFIED_NOT_SELLER",
                "next_action": "NURTURE",
                "channel": "NONE",
                "reason": "Not a verified real estate seller with verified owner/phone",
                "is_actionable": False,
            }

        # Check existing state
        state = lead.get("status") or lead.get("crm_stage") or "QUEUED"
        if state in {"CONTACTED", "QUALIFIED", "INTERESTED", "CALLBACK_REQUESTED"}:
            return {
                "lead_id": lead_id,
                "status": state,
                "next_action": "QUALIFY" if state == "CONTACTED" else "SEND_OFFER" if state == "QUALIFIED" else "CALL_BACK",
                "channel": "PHONE",
                "reason": f"Active engagement in stage {state}",
                "is_actionable": True,
            }

        if state in {"NOT_INTERESTED", "WRONG_PERSON", "INVALID"}:
            return {
                "lead_id": lead_id,
                "status": state,
                "next_action": "NURTURE",
                "channel": "NONE",
                "reason": f"Lead marked {state}",
                "is_actionable": False,
            }

        # Check cascade history
        history = self.get_lead_history(lead_id)
        executed_stages = {h.get("stage") for h in history if h.get("status") in {"SENT", "DELIVERED", "CONFIRMED"}}
        last_event = history[-1] if history else None

        raw_email = str(lead.get("email") or (lead.get("details") or {}).get("email") or "").strip()
        has_email = bool(raw_email and "@" in raw_email and "." in raw_email)
        phone = lead.get("phone")

        now = datetime.now(timezone.utc)

        # Stage 0: Initial Outreach
        if "DAY_0_INITIAL" not in executed_stages:
            return {
                "lead_id": lead_id,
                "status": "QUEUED",
                "stage": "DAY_0_INITIAL",
                "next_action": "SEND_WHATSAPP",
                "channel": "WHATSAPP",
                "has_email_fallback": has_email,
                "phone": phone,
                "email": raw_email if has_email else None,
                "reason": "Initial outreach due (Day 0)",
                "is_actionable": True,
            }

        # Subsequent stages (Day 1, Day 3, Day 5)
        last_ts_str = last_event.get("timestamp") if last_event else None
        last_ts = datetime.fromisoformat(last_ts_str) if last_ts_str else now - timedelta(days=10)
        hours_elapsed = (now - last_ts).total_seconds() / 3600.0

        for stage in CADENCE_STAGES[1:]:
            if stage not in executed_stages:
                required_interval = 24.0  # 24 hours between touches minimum
                if hours_elapsed >= required_interval:
                    return {
                        "lead_id": lead_id,
                        "status": "WHATSAPP_FOLLOWUP_DUE",
                        "stage": stage,
                        "next_action": "WHATSAPP_FOLLOWUP",
                        "channel": "WHATSAPP",
                        "has_email_fallback": has_email,
                        "phone": phone,
                        "email": raw_email if has_email else None,
                        "reason": f"Follow-up {stage} due ({hours_elapsed:.1f}h elapsed)",
                        "is_actionable": True,
                    }
                else:
                    return {
                        "lead_id": lead_id,
                        "status": "WAITING_RESPONSE",
                        "stage": stage,
                        "next_action": "WAIT_FOR_RESPONSE",
                        "channel": "WHATSAPP",
                        "hours_remaining": max(0.0, required_interval - hours_elapsed),
                        "reason": f"Waiting for response before {stage} ({hours_elapsed:.1f}h / {required_interval}h)",
                        "is_actionable": False,
                    }

        # If all WhatsApp stages exhausted:
        if has_email and "EMAIL_FINAL_TOUCH" not in executed_stages:
            return {
                "lead_id": lead_id,
                "status": "EMAIL_FALLBACK_ELIGIBLE",
                "stage": "EMAIL_FINAL_TOUCH",
                "next_action": "SEND_EMAIL",
                "channel": "EMAIL",
                "email": raw_email,
                "reason": "WhatsApp exhausted, falling back to verified email",
                "is_actionable": True,
            }

        return {
            "lead_id": lead_id,
            "status": "CASCADE_COMPLETE",
            "next_action": "CALL_BACK",
            "channel": "PHONE",
            "reason": "Outbound cascade complete, secondary phone check-in scheduled",
            "is_actionable": True,
        }

    def record_cascade_event(
        self,
        lead_id: str,
        channel: str,
        stage: str,
        status: str,
        notes: str = "",
        provider_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Idempotently records an outbound event in the cascade log and GTM sales ledger.
        """
        history = self._load_history()

        # Idempotency check: prevent duplicate send for same lead_id + stage + channel if already SENT
        for h in history:
            if h.get("lead_id") == lead_id and h.get("stage") == stage and h.get("channel") == channel and h.get("status") in {"SENT", "DELIVERED"}:
                return {
                    "status": "IDEMPOTENT_SKIPPED",
                    "reason": f"Event for {lead_id} {stage} via {channel} already recorded.",
                    "existing_event": h,
                }

        now_iso = datetime.now(timezone.utc).isoformat()
        event_record = {
            "lead_id": lead_id,
            "channel": channel,
            "stage": stage,
            "status": status,
            "timestamp": now_iso,
            "notes": notes,
            "provider_result": provider_result or {},
        }
        history.append(event_record)
        self._save_history(history)

        # Update GTM sales ledger
        self.ledger.record_event(
            prospect_id=lead_id,
            agent="SELLER_CASCADE_ENGINE",
            channel=channel,
            previous_state="CASCADE_QUEUED",
            new_state=f"{channel}_{status}",
            action=f"SELLER_CASCADE_{stage}",
            evidence=event_record,
            next_action="WAIT_FOR_RESPONSE" if status == "SENT" else "FOLLOW_UP",
            notes=notes,
        )


        return {"status": "RECORDED", "event": event_record}

    def execute_next_cascade_step(self, lead_id: str, live: bool = False) -> Dict[str, Any]:
        """
        Evaluates and executes the next cascade step for a given seller lead.
        """
        leads = self.writer.read_leads()
        target = next((l for l in leads if str(l.get("id")) == str(lead_id)), None)
        if not target:
            raise ValueError(f"Lead ID '{lead_id}' not found.")

        decision = self.determine_next_action(target)
        if not decision["is_actionable"]:
            return {"status": "SKIPPED", "decision": decision}

        channel = decision["channel"]
        stage = decision.get("stage", "DAY_0_INITIAL")
        owner = target.get("contact") or target.get("owner_name") or "Owner"
        prop = target.get("address") or target.get("property_address") or target.get("company") or "Property"

        templates = get_seller_templates(owner, prop).get(stage, get_seller_templates(owner, prop)["DAY_0_INITIAL"])

        if channel == "WHATSAPP":
            clean_phone = _digits(target.get("phone", ""))
            msg = templates["whatsapp"]
            encoded = urllib.parse.quote(msg)
            wa_link = f"https://wa.me/{clean_phone}?text={encoded}"

            # If automated sender is not configured, generate link ready event
            res = self.record_cascade_event(
                lead_id=lead_id,
                channel="WHATSAPP",
                stage=stage,
                status="LINK_READY" if not live else "SENT",
                notes=f"Generated 1-click WhatsApp bridge for {owner} ({stage})",
                provider_result={"wa_link": wa_link, "phone": target.get("phone")},
            )
            return {
                "status": "WHATSAPP_DISPATCH_READY",
                "lead_id": lead_id,
                "owner": owner,
                "phone": target.get("phone"),
                "stage": stage,
                "wa_link": wa_link,
                "message": msg,
                "event": res,
            }

        elif channel == "EMAIL":
            to_email = decision.get("email")
            if not to_email:
                return {"status": "EMAIL_FAILED_NO_ADDRESS", "reason": "No verified email for seller"}

            email_subj = templates["email_subject"]
            email_body = templates["email_body"]

            # Dispatch via GmailDispatchAdapter
            dispatch_res = self.gmail.send_cold_email(
                entity_id=lead_id,
                to_email=to_email,
                subject=email_subj,
                body=email_body,
                opportunity={"property": prop, "lane": "REAL_ESTATE_SELLER_CASCADE"},
            )

            status_str = "SENT" if dispatch_res.get("status") == "SENT" else "DRY_RUN"
            res = self.record_cascade_event(
                lead_id=lead_id,
                channel="EMAIL",
                stage=stage,
                status=status_str,
                notes=f"Email dispatch to {to_email} ({stage})",
                provider_result=dispatch_res,
            )
            return {
                "status": f"EMAIL_{status_str}",
                "lead_id": lead_id,
                "owner": owner,
                "to_email": to_email,
                "stage": stage,
                "dispatch_result": dispatch_res,
                "event": res,
            }

        return {"status": "PHONE_CALLBACK_SCHEDULED", "decision": decision}

    def generate_cascade_status_report(self) -> Dict[str, Any]:
        """Generates a comprehensive status report across all 155 seller leads."""
        leads = self.writer.read_leads()
        sellers = [l for l in leads if is_real_estate_seller(l) and not is_lead_suppressed(l) and has_verified_owner_and_phone(l)]
        sellers.sort(key=lambda x: (x.get("queue_rank") if isinstance(x.get("queue_rank"), int) else 999999))

        actionable = []
        waiting = []
        complete = []

        for s in sellers:
            dec = self.determine_next_action(s)
            item = {
                "rank": s.get("queue_rank"),
                "lead_id": s.get("id"),
                "owner": s.get("contact") or s.get("owner_name"),
                "phone": s.get("phone"),
                "email": s.get("email"),
                "property": s.get("company") or s.get("address"),
                "next_action": dec["next_action"],
                "channel": dec["channel"],
                "stage": dec.get("stage", "N/A"),
                "reason": dec["reason"],
            }
            if dec["is_actionable"]:
                actionable.append(item)
            elif dec["status"] == "WAITING_RESPONSE":
                waiting.append(item)
            else:
                complete.append(item)

        lines = [
            "# REAL ESTATE SELLER FOLLOW-UP CASCADE STATUS REPORT",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Total Verified Sellers:** {len(sellers)}",
            f"**Actionable Next Tasks:** {len(actionable)}",
            f"**In Waiting Window:** {len(waiting)}",
            f"**Cascade Completed / Closed:** {len(complete)}",
            "",
            "---",
            "",
            "## TOP 10 IMMEDIATE ACTIONABLE TASKS",
            "| Rank | Lead ID | Owner | Phone | Channel | Stage | Next Action |",
            "|---|---|---|---|---|---|---|",
        ]

        for item in actionable[:10]:
            lines.append(f"| #{item['rank']} | `{item['lead_id']}` | {item['owner']} | `{item['phone']}` | **{item['channel']}** | `{item['stage']}` | `{item['next_action']}` |")

        lines.extend([
            "",
            "---",
            "",
            "## EXECUTION INSTRUCTIONS",
            "1. Process next actionable seller: `python MBM/LeadEngine/seller_followup_cascade.py --next`",
            "2. Execute single lead step: `python MBM/LeadEngine/seller_followup_cascade.py --execute --lead-id <ID>`",
            "3. Record operator confirmation: `python MBM/LeadEngine/seller_batch_runner.py --record --lead-id <ID> --disposition <DISP>`",
            ""
        ])

        CASCADE_STATUS_DOC.parent.mkdir(parents=True, exist_ok=True)
        CASCADE_STATUS_DOC.write_text("\n".join(lines), encoding="utf-8")

        return {
            "total_sellers": len(sellers),
            "actionable_count": len(actionable),
            "waiting_count": len(waiting),
            "complete_count": len(complete),
            "top_actionable": actionable[:10],
            "doc_path": str(CASCADE_STATUS_DOC),
        }


def main():
    parser = argparse.ArgumentParser(description="MBM Real Estate Seller Follow-Up Cascade Engine")
    parser.add_argument("--next", action="store_true", help="Display the next actionable cascade target")
    parser.add_argument("--status", action="store_true", help="Generate cascade status report")
    parser.add_argument("--execute", action="store_true", help="Execute the next cascade step for a lead")
    parser.add_argument("--lead-id", type=str, help="Lead ID to execute cascade for")
    parser.add_argument("--live", action="store_true", help="Execute in live mode (default: DRY-RUN)")
    args = parser.parse_args()

    cascade = SellerFollowupCascade()

    if args.status or (not args.next and not args.execute and not args.lead_id):
        res = cascade.generate_cascade_status_report()
        print("=" * 80)
        print(f"SELLER CASCADE REPORT GENERATED: {res['doc_path']}")
        print(f"Total Sellers: {res['total_sellers']} | Actionable: {res['actionable_count']} | Waiting: {res['waiting_count']}")
        print("=" * 80)
        return

    if args.next:
        leads = cascade.writer.read_leads()
        sellers = [l for l in leads if is_real_estate_seller(l) and not is_lead_suppressed(l) and has_verified_owner_and_phone(l)]
        sellers.sort(key=lambda x: (x.get("queue_rank") if isinstance(x.get("queue_rank"), int) else 999999))

        next_actionable = None
        for s in sellers:
            dec = cascade.determine_next_action(s)
            if dec["is_actionable"]:
                next_actionable = (s, dec)
                break

        if not next_actionable:
            print("[INFO] No immediate actionable cascade tasks. All leads are current or in response windows.")
            return

        lead, dec = next_actionable
        owner = lead.get("contact") or lead.get("owner_name")
        first_name = owner.split()[0] if owner else "there"
        phone = lead.get("phone")
        prop = lead.get("address") or lead.get("property_address") or lead.get("company")
        stage = dec.get("stage", "DAY_0_INITIAL")
        channel = dec["channel"]
        templates = get_seller_templates(owner, prop).get(stage, get_seller_templates(owner, prop)["DAY_0_INITIAL"])

        clean_phone = _digits(phone)
        msg = templates["whatsapp"]
        encoded = urllib.parse.quote(msg)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded}"

        print("=" * 80)
        print(f"[*] NEXT ACTIONABLE CASCADE SELLER: #{lead.get('queue_rank')} (Stage: {stage} | Channel: {channel})")
        print("=" * 80)
        print(f"  PROPERTY:  {prop}")
        print(f"  OWNER:     {owner}")
        print(f"  PHONE:     {phone} (Verified)")
        print(f"  ACTION:    {dec['next_action']} ({dec['reason']})")
        print(f"  LEAD ID:   {lead.get('id')}")
        print("--------------------------------------------------------------------------------")
        if channel == "WHATSAPP":
            print(f"  1-CLICK WHATSAPP: {wa_link}")
            print(f"  DIRECT CALL:      tel:{phone}")
            print("  MESSAGE:")
            print(f"    '{msg}'")
        elif channel == "EMAIL":
            print(f"  TO EMAIL:         {dec.get('email')}")
            print(f"  SUBJECT:          {templates['email_subject']}")
        print("--------------------------------------------------------------------------------")
        print("EXECUTE & RECORD:")
        print(f"  python MBM/LeadEngine/seller_followup_cascade.py --execute --lead-id {lead.get('id')}")
        print(f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead.get('id')} --disposition CONTACTED")
        print("=" * 80)
        return

    if args.execute:
        if not args.lead_id:
            print("[ERROR] --lead-id is required when executing.")
            sys.exit(1)
        res = cascade.execute_next_cascade_step(args.lead_id, live=args.live)
        print(f"[OK] Cascade step executed for {args.lead_id}: {res['status']}")
        if res.get("wa_link"):
            print(f"     WhatsApp Link: {res['wa_link']}")


if __name__ == "__main__":
    main()
