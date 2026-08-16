"""
DYNAMIC EVIDENCE-DRIVEN CONVERSATION ENGINE
=============================================================================
Transforms static sales scripts into an adaptive, listening conversation brain.

Pipeline:
  LISTEN -> CLASSIFY -> ASK BEST NEXT QUESTION -> QUANTIFY PAIN ->
  MATCH AI SOLUTION -> HANDLE OBJECTION -> ADVANCE TO NEXT STEP
=============================================================================
"""

import re
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from MBM.LeadEngine.gtm.learning import GtmLearningEngine, OutcomeType


# ---------------------------------------------------------------------------
# 1. Enums & States
# ---------------------------------------------------------------------------

class ConversationMode(str, Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"


class ConversationState(str, Enum):
    CALL_OPEN = "CALL_OPEN"
    PERMISSION = "PERMISSION"
    DISCOVERY = "DISCOVERY"
    PAIN_IDENTIFIED = "PAIN_IDENTIFIED"
    PAIN_QUANTIFIED = "PAIN_QUANTIFIED"
    SOLUTION_FIT = "SOLUTION_FIT"
    ROI = "ROI"
    OBJECTION = "OBJECTION"
    COMMITMENT = "COMMITMENT"
    MEETING = "MEETING"
    FOLLOWUP = "FOLLOWUP"
    ENDED = "ENDED"


class ConversationActionType(str, Enum):
    ASK = "ASK"
    CLARIFY = "CLARIFY"
    QUANTIFY = "QUANTIFY"
    REFLECT = "REFLECT"
    CHALLENGE = "CHALLENGE"
    EDUCATE = "EDUCATE"
    POSITION = "POSITION"
    HANDLE_OBJECTION = "HANDLE_OBJECTION"
    CONFIRM = "CONFIRM"
    CTA = "CTA"
    END_CALL = "END_CALL"
    SCHEDULE_FOLLOWUP = "SCHEDULE_FOLLOWUP"


class PatternInterruptType(str, Enum):
    DIRECT = "DIRECT"
    DIAGNOSTIC = "DIAGNOSTIC"
    PERMISSION = "PERMISSION"
    CURIOSITY = "CURIOSITY"
    SIGNAL_BASED = "SIGNAL_BASED"


class QuestionCategory(str, Enum):
    CURRENT_STATE = "CURRENT_STATE"
    WORKFLOW = "WORKFLOW"
    VOLUME = "VOLUME"
    FREQUENCY = "FREQUENCY"
    COST = "COST"
    CONSEQUENCE = "CONSEQUENCE"
    BOTTLENECK = "BOTTLENECK"
    CURRENT_TOOL = "CURRENT_TOOL"
    STAFFING = "STAFFING"
    TIMING = "TIMING"
    DECISION_PROCESS = "DECISION_PROCESS"


class PainSourceType(str, Enum):
    PROSPECT_STATED = "PROSPECT_STATED"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class ProspectClassification(str, Enum):
    INTERESTED = "INTERESTED"
    CURIOUS = "CURIOUS"
    NEUTRAL = "NEUTRAL"
    BUSY = "BUSY"
    SKEPTICAL = "SKEPTICAL"
    OBJECTION = "OBJECTION"
    PRICE_CONCERN = "PRICE_CONCERN"
    AUTHORITY_CONCERN = "AUTHORITY_CONCERN"
    TIMING_CONCERN = "TIMING_CONCERN"
    ALREADY_SOLVED = "ALREADY_SOLVED"
    NOT_INTERESTED = "NOT_INTERESTED"
    WRONG_PERSON = "WRONG_PERSON"
    WRONG_NUMBER = "WRONG_NUMBER"
    OWNER_CONFIRMATION = "OWNER_CONFIRMATION"
    MEETING_INTENT = "MEETING_INTENT"


class ObjectionCategory(str, Enum):
    PRICE = "PRICE"
    TIMING = "TIMING"
    TRUST = "TRUST"
    AI_SKEPTICISM = "AI_SKEPTICISM"
    ALREADY_HAVE_SOLUTION = "ALREADY_HAVE_SOLUTION"
    DO_IT_INTERNALLY = "DO_IT_INTERNALLY"
    NO_NEED = "NO_NEED"
    NO_BUDGET = "NO_BUDGET"
    AUTHORITY = "AUTHORITY"
    PRIORITY = "PRIORITY"
    SECURITY = "SECURITY"
    INTEGRATION = "INTEGRATION"
    STAFF = "STAFF"


class DispositionOutcome(str, Enum):
    NO_FIT = "NO_FIT"
    NURTURE = "NURTURE"
    FOLLOWUP = "FOLLOWUP"
    QUALIFIED = "QUALIFIED"
    MEETING_READY = "MEETING_READY"


# ---------------------------------------------------------------------------
# 2. Data Models
# ---------------------------------------------------------------------------

@dataclass
class PainModel:
    pain_type: str = "Unknown"
    frequency: str = "Daily"
    volume: str = "Unknown"
    time_cost: str = "Unknown"
    labor_cost: str = "Unknown"
    revenue_impact_usd: float = 0.0
    missed_opportunity: str = "Unknown"
    urgency: float = 0.5
    confidence: float = 0.5
    source_type: PainSourceType = PainSourceType.UNKNOWN


@dataclass
class ConversationAction:
    action: ConversationActionType
    suggested_language: str
    reason: str
    state_transition: str
    confidence: float
    evidence_used: str
    question_category: Optional[QuestionCategory] = None
    objection_category: Optional[ObjectionCategory] = None


@dataclass
class ConversationMemory:
    questions_asked: List[str] = field(default_factory=list)
    answers: List[str] = field(default_factory=list)
    pain_confirmed: bool = False
    pain_score: float = 0.0
    objections: List[str] = field(default_factory=list)
    solutions_discussed: List[str] = field(default_factory=list)
    prospect_language: List[str] = field(default_factory=list)
    next_step: str = "DISCOVERY"
    identity_state: str = "IDENTITY_UNCONFIRMED"
    conversation_summary: str = ""
    pain_model: PainModel = field(default_factory=PainModel)
    engagement_turns: int = 0


# ---------------------------------------------------------------------------
# 3. Dynamic Conversation Engine
# ---------------------------------------------------------------------------

class DynamicConversationEngine:
    """
    Evidence-driven conversation brain that listens, classifies, diagnoses,
    and returns the optimal next conversational move.
    """

    def __init__(self, learning_engine: Optional[GtmLearningEngine] = None):
        self.learning_engine = learning_engine or GtmLearningEngine()

    def determine_mode(self, opportunity: Dict[str, Any]) -> ConversationMode:
        """Select COLD, WARM, or HOT mode based on intent score/tier."""
        tier = (opportunity.get("intent_tier") or opportunity.get("tier") or "").upper()
        score = float(opportunity.get("intent_score") or 0.0)

        if tier == "HOT" or score >= 90:
            return ConversationMode.HOT
        elif tier in {"HIGH INTENT", "WARM"} or score >= 70:
            return ConversationMode.WARM
        return ConversationMode.COLD

    def classify_response(self, text: Optional[str]) -> Tuple[ProspectClassification, Dict[str, Any]]:
        """
        Classify prospect response and extract key intent/objection signals.
        """
        if not text or not text.strip():
            return ProspectClassification.NEUTRAL, {}

        t = text.lower()
        extracted = {}

        # Wrong Person / Wrong Number
        if any(w in t for w in ["wrong number", "no one by that name", "wrong phone", "remove this number"]):
            return ProspectClassification.WRONG_NUMBER, {"disposition": "WRONG_NUMBER"}
        if any(w in t for w in ["wrong person", "don't work here", "no longer with", "left the company", "not the owner", "i'm just a tenant"]):
            return ProspectClassification.WRONG_PERSON, {"disposition": "WRONG_PERSON"}

        # Meeting Intent
        if any(w in t for w in ["send an invite", "let's do thursday", "let's meet", "book it", "sounds good let's schedule", "calendar", "google meet", "zoom"]):
            return ProspectClassification.MEETING_INTENT, {"timing": "Immediate", "next_step": "MEETING"}

        # Owner Confirmation
        if any(w in t for w in ["speaking", "this is him", "this is her", "this is marcus", "this is derek", "i own the company", "i'm the managing partner"]):
            return ProspectClassification.OWNER_CONFIRMATION, {"authority": "CONFIRMED_OWNER"}

        # Busy
        if any(w in t for w in [
            "in the middle of something", "driving", "bad time", "call me back",
            "in a meeting", "busy right now", "job site", "can't talk", "cannot talk",
            "on a job", "not a good time", "tied up"
        ]):
            return ProspectClassification.BUSY, {"urgency": "LOW_NOW"}

        # Not Interested
        if any(w in t for w in ["not interested", "stop calling", "take me off", "don't call again", "no thanks"]):
            return ProspectClassification.NOT_INTERESTED, {"disposition": "NURTURE"}

        # Objections
        if any(w in t for w in ["expensive", "cost", "price", "how much", "budget", "more than we spend"]):
            return ProspectClassification.PRICE_CONCERN, {"objection": "PRICE"}
        if any(w in t for w in ["already have", "already use", "we use servicetitan", "we use jobber", "we have a receptionist", "have someone"]):
            return ProspectClassification.ALREADY_SOLVED, {"objection": "ALREADY_HAVE_SOLUTION"}
        if any(w in t for w in ["not sure", "robot", "sounds robotic", "ai doesn't work", "skeptical", "hallucinate"]):
            return ProspectClassification.SKEPTICAL, {"objection": "AI_SKEPTICISM"}
        if any(w in t for w in ["need to check with partner", "not my decision", "talk to my boss"]):
            return ProspectClassification.AUTHORITY_CONCERN, {"objection": "AUTHORITY"}

        # Interest / Curiosity
        if any(w in t for w in ["how does it work", "tell me more", "what do you do", "what is this about", "how so"]):
            return ProspectClassification.CURIOUS, {"interest": "HIGH"}
        if any(w in t for w in ["yes", "we miss calls", "it is a bottleneck", "definitely", "struggling with that", "overwhelmed"]):
            return ProspectClassification.INTERESTED, {"interest": "VERY_HIGH", "pain_confirmed": True}

        return ProspectClassification.NEUTRAL, extracted

    def get_opening(
        self,
        opportunity: Dict[str, Any],
        mode: ConversationMode,
        interrupt_type: PatternInterruptType = PatternInterruptType.PERMISSION,
    ) -> ConversationAction:
        """Generate evidence-driven conversational opening."""
        dm = opportunity.get("decision_maker") or "there"
        company = opportunity.get("company") or "your company"
        pain = opportunity.get("pain") or "after-hours emergency call overflow"
        evidence_claim = opportunity.get("evidence", {}).get("claim") if isinstance(opportunity.get("evidence"), dict) else opportunity.get("why_this_company", "")

        if mode == ConversationMode.HOT:
            lang = (
                f"Hi {dm}, Omar with TranchAI. Calling directly regarding {company}'s active bottleneck with {pain}—"
                f"have you got 30 seconds to calibrate how you're handling those right now?"
            )
            reason = "Hot buyer opening: direct validation of known operational bottleneck."
            state_tr = f"{ConversationState.CALL_OPEN.value} -> {ConversationState.DISCOVERY.value}"
        elif mode == ConversationMode.WARM:
            lang = (
                f"Hey {dm}, Omar here. I know I'm calling out of the blue. "
                f"Saw {company}'s recent operations in your market and noticed you're dealing with high-volume {pain}. "
                f"How is your dispatch team currently managing that volume?"
            )
            reason = "Warm buyer opening: evidence-backed observation with single discovery question."
            state_tr = f"{ConversationState.CALL_OPEN.value} -> {ConversationState.DISCOVERY.value}"
        else:  # COLD
            if interrupt_type == PatternInterruptType.PERMISSION:
                lang = f"Hey {dm}, Omar with TranchAI. I know I caught you out of the blue. Give me 20 seconds and you can tell me if I'm wasting your time?"
            elif interrupt_type == PatternInterruptType.DIRECT:
                lang = f"Hi {dm}, I'll be brief. I'm calling because of one operational issue I think {company} is dealing with regarding {pain}. Have you got 30 seconds?"
            elif interrupt_type == PatternInterruptType.DIAGNOSTIC:
                lang = f"Hi {dm}, quick question about your current front-office workflow at {company} when after-hours calls come in—who handles those today?"
            else:
                lang = f"Hi {dm}, Omar with TranchAI. Quick 20-second question—how is {company} currently handling unworked lead follow-ups?"

            reason = f"Cold opening ({interrupt_type.value}): Pattern interrupt earning permission without pitching."
            state_tr = f"{ConversationState.CALL_OPEN.value} -> {ConversationState.PERMISSION.value}"

        return ConversationAction(
            action=ConversationActionType.ASK,
            suggested_language=lang,
            reason=reason,
            state_transition=state_tr,
            confidence=0.92,
            evidence_used=evidence_claim or pain,
            question_category=QuestionCategory.WORKFLOW,
        )

    def next_action(
        self,
        opportunity: Dict[str, Any],
        conversation_state: ConversationState,
        last_prospect_message: Optional[str] = None,
        memory: Optional[ConversationMemory] = None,
    ) -> ConversationAction:
        """
        Master decision engine: Given current state, prospect input, and conversation memory,
        computes and returns the next best conversational action.
        """
        if memory is None:
            memory = ConversationMemory()

        mode = self.determine_mode(opportunity)
        dm = opportunity.get("decision_maker") or "there"
        company = opportunity.get("company") or "your company"
        pain = opportunity.get("pain") or "missed emergency calls"
        ai_assistant = opportunity.get("recommended_ai_assistant") or "24/7 AI Emergency Call Concierge"
        retainer = float(opportunity.get("monthly_retainer_usd") or 2000.0)
        sku = opportunity.get("sku") or "AI-ASSISTANT-VIP-RETAINER"

        # Step 1: Classify prospect utterance
        classification, extracted = self.classify_response(last_prospect_message)
        if last_prospect_message:
            memory.answers.append(last_prospect_message)
            memory.engagement_turns += 1
            # Extract prospect terminology
            words = [w for w in re.findall(r"\b\w+\b", last_prospect_message) if len(w) > 4]
            memory.prospect_language.extend(words[:3])

        # Step 2: Handle Terminal / Suppression Classifications
        if classification == ProspectClassification.WRONG_NUMBER:
            return ConversationAction(
                action=ConversationActionType.END_CALL,
                suggested_language="Understood, apologies for the disturbance. Removing this number from our registry immediately.",
                reason="Wrong number identified. Triggering suppression gate.",
                state_transition=f"{conversation_state.value} -> {ConversationState.ENDED.value}",
                confidence=0.99,
                evidence_used="Prospect stated wrong number",
            )

        if classification == ProspectClassification.WRONG_PERSON:
            return ConversationAction(
                action=ConversationActionType.CLARIFY,
                suggested_language=f"Got it, apologies. Who is the managing owner or operations lead handling dispatch at {company} nowadays?",
                reason="Wrong person identified. Clarifying correct authority before updating identity state.",
                state_transition=f"{conversation_state.value} -> {ConversationState.DISCOVERY.value}",
                confidence=0.95,
                evidence_used="Prospect stated non-owner / wrong person",
            )

        if classification == ProspectClassification.BUSY:
            return ConversationAction(
                action=ConversationActionType.SCHEDULE_FOLLOWUP,
                suggested_language=f"Totally understand you're in the middle of something. What's a better time later today or tomorrow morning for a 2-minute check-in?",
                reason="Prospect is busy. Respecting timing and asking for specific callback slot.",
                state_transition=f"{conversation_state.value} -> {ConversationState.FOLLOWUP.value}",
                confidence=0.90,
                evidence_used="Prospect indicated busy state",
            )

        if classification == ProspectClassification.NOT_INTERESTED:
            return ConversationAction(
                action=ConversationActionType.END_CALL,
                suggested_language="Understood. Thanks for your time, have a great rest of your week.",
                reason="Prospect stated not interested. Ending call gracefully and moving to nurture.",
                state_transition=f"{conversation_state.value} -> {ConversationState.ENDED.value}",
                confidence=0.95,
                evidence_used="Explicit opt-out / not interested",
            )

        # Step 3: Handle Objections via ACKNOWLEDGE -> CLARIFY -> ISOLATE -> RESPOND -> CHECK
        if classification in {ProspectClassification.PRICE_CONCERN, ProspectClassification.ALREADY_SOLVED, ProspectClassification.SKEPTICAL, ProspectClassification.AUTHORITY_CONCERN}:
            if classification == ProspectClassification.ALREADY_SOLVED:
                lang = (
                    f"Makes total sense you have a system in place. When your front desk is already tied up on another line or after hours, "
                    f"what percentage of callers end up hanging up or leaving a voicemail that never gets called back?"
                )
                reason = "Objection: Already have solution. Acknowledging and isolating the overflow/after-hours gap."
                obj_cat = ObjectionCategory.ALREADY_HAVE_SOLUTION
            elif classification == ProspectClassification.PRICE_CONCERN:
                lang = (
                    f"Fair question on cost. Most operators find that recovering even 2 or 3 missed jobs a month covers the entire ${retainer:,.0f}/mo fee. "
                    f"What is the average value of a typical completed job for {company}?"
                )
                reason = "Objection: Price concern. Reframing cost as ROI against job value."
                obj_cat = ObjectionCategory.PRICE
            elif classification == ProspectClassification.SKEPTICAL:
                lang = (
                    f"I hear you—there are a lot of clunky bots out there. This uses ultra-low latency neural voice models that sound identical to an in-house dispatcher. "
                    f"Would you be open to hearing a 30-second live test recording on a demo line?"
                )
                reason = "Objection: AI skepticism. Validating concern and offering immediate evidence via live test."
                obj_cat = ObjectionCategory.AI_SKEPTICISM
            else:
                lang = f"Understood on partner approval. If you and your partner saw a live test recovering 5+ missed calls a week, would it make sense to review the 5-minute brief together?"
                reason = "Objection: Authority/Partner. Offering joint stakeholder packet."
                obj_cat = ObjectionCategory.AUTHORITY

            memory.objections.append(obj_cat.value)

            return ConversationAction(
                action=ConversationActionType.HANDLE_OBJECTION,
                suggested_language=lang,
                reason=reason,
                state_transition=f"{conversation_state.value} -> {ConversationState.OBJECTION.value}",
                confidence=0.91,
                evidence_used=pain,
                objection_category=obj_cat,
            )

        # Step 4: Meeting Intent Captured
        if classification == ProspectClassification.MEETING_INTENT:
            return ConversationAction(
                action=ConversationActionType.CONFIRM,
                suggested_language=f"Perfect. I'll send a Google Meet invite for Thursday at 10 AM to your email. We'll map the assistant directly into your workflow in 15 minutes.",
                reason="Prospect signaled meeting intent. Locking down calendar slot.",
                state_transition=f"{conversation_state.value} -> {ConversationState.MEETING.value}",
                confidence=0.98,
                evidence_used="Prospect requested meeting / calendar invite",
            )

        # Step 5: State Machine Conversational Progression
        if conversation_state == ConversationState.CALL_OPEN:
            return self.get_opening(opportunity, mode)

        elif conversation_state == ConversationState.PERMISSION:
            # Granted permission -> Move to Discovery Question 1
            lang = f"Appreciate that. We noticed Texas operators in {opportunity.get('industry', 'your vertical')} losing high-ticket jobs due to {pain}. How are you handling those today?"
            return ConversationAction(
                action=ConversationActionType.ASK,
                suggested_language=lang,
                reason="Permission granted. Asking core workflow discovery question.",
                state_transition=f"{ConversationState.PERMISSION.value} -> {ConversationState.DISCOVERY.value}",
                confidence=0.92,
                evidence_used=pain,
                question_category=QuestionCategory.WORKFLOW,
            )

        elif conversation_state == ConversationState.DISCOVERY:
            # If pain is confirmed -> Quantify impact
            if classification == ProspectClassification.INTERESTED or "QUANTIFY" not in memory.questions_asked:
                memory.pain_confirmed = True
                memory.questions_asked.append("QUANTIFY")
                lang = f"Got it. Roughly how many unworked calls or estimate requests are coming through in a normal week?"
                return ConversationAction(
                    action=ConversationActionType.QUANTIFY,
                    suggested_language=lang,
                    reason="Pain acknowledged. Quantifying weekly volume to build ROI basis.",
                    state_transition=f"{ConversationState.DISCOVERY.value} -> {ConversationState.PAIN_QUANTIFIED.value}",
                    confidence=0.93,
                    evidence_used=pain,
                    question_category=QuestionCategory.VOLUME,
                )
            else:
                lang = f"What happens when the team can't get to those inquiries quickly enough?"
                return ConversationAction(
                    action=ConversationActionType.ASK,
                    suggested_language=lang,
                    reason="Deepening discovery into business consequence.",
                    state_transition=f"{ConversationState.DISCOVERY.value} -> {ConversationState.PAIN_IDENTIFIED.value}",
                    confidence=0.90,
                    evidence_used=pain,
                    question_category=QuestionCategory.CONSEQUENCE,
                )

        elif conversation_state in {ConversationState.PAIN_IDENTIFIED, ConversationState.PAIN_QUANTIFIED}:
            # Reflection Engine: Reflect pain back before introducing AI fit
            lang = (
                f"So if I'm hearing you right, the issue isn't lead volume—it's that high-value opportunities slip through when dispatch is tied up. "
                f"Is that fair?"
            )
            return ConversationAction(
                action=ConversationActionType.REFLECT,
                suggested_language=lang,
                reason="Reflecting problem back to build agreement before presenting AI assistant.",
                state_transition=f"{conversation_state.value} -> {ConversationState.SOLUTION_FIT.value}",
                confidence=0.94,
                evidence_used=pain,
            )

        elif conversation_state == ConversationState.SOLUTION_FIT:
            # AI Fit Transition
            lang = (
                f"That's exactly what we automated. We deployed a custom {ai_assistant} that answers on the 1st ring, "
                f"qualifies the inquiry, and books appointments directly into your schedule. "
                f"Would you be open to a 2-minute simulation showing how it handles a live scenario?"
            )
            return ConversationAction(
                action=ConversationActionType.POSITION,
                suggested_language=lang,
                reason="AI Fit matched to confirmed pain. Proposing 2-minute micro-commitment.",
                state_transition=f"{ConversationState.SOLUTION_FIT.value} -> {ConversationState.COMMITMENT.value}",
                confidence=0.93,
                evidence_used=ai_assistant,
            )

        elif conversation_state in {ConversationState.ROI, ConversationState.COMMITMENT}:
            # Final CTA / Meeting Pitch
            if mode == ConversationMode.HOT or classification in {ProspectClassification.INTERESTED, ProspectClassification.CURIOUS}:
                lang = f"Let's do a 15-minute diagnostic on Google Meet this Thursday at 10 AM to test the neural voice agent live against your current process. Would that work?"
            else:
                lang = f"Would it be helpful if I sent over a 1-page architecture brief and benchmark audio sample to {opportunity.get('email', 'your email')}?"

            return ConversationAction(
                action=ConversationActionType.CTA,
                suggested_language=lang,
                reason="Closing turn: matching CTA commitment level to prospect engagement.",
                state_transition=f"{conversation_state.value} -> {ConversationState.MEETING.value}",
                confidence=0.95,
                evidence_used="Confirmed pain and solution fit",
            )

        # Default fallback: Ask discovery
        return ConversationAction(
            action=ConversationActionType.ASK,
            suggested_language=f"How are you currently handling after-hours call overflow at {company}?",
            reason="Fallback discovery turn.",
            state_transition=f"{conversation_state.value} -> {ConversationState.DISCOVERY.value}",
            confidence=0.85,
            evidence_used=pain,
            question_category=QuestionCategory.WORKFLOW,
        )

    def calculate_conversation_score(self, memory: ConversationMemory) -> Dict[str, Any]:
        """
        Evaluate full interaction and compute structured conversation metrics.
        """
        turns = memory.engagement_turns
        pain_confirmed = memory.pain_confirmed
        objection_count = len(memory.objections)

        engagement_score = min(100.0, turns * 20.0)
        pain_score = 90.0 if pain_confirmed else 40.0
        intent_score = 95.0 if memory.next_step == "MEETING" else (70.0 if pain_confirmed else 30.0)
        authority_score = 90.0 if "CONFIRMED" in memory.identity_state else 60.0
        urgency_score = 85.0 if pain_confirmed else 45.0
        next_step_score = 100.0 if memory.next_step == "MEETING" else 50.0

        avg_score = (engagement_score + pain_score + intent_score + authority_score + urgency_score + next_step_score) / 6.0

        if memory.next_step == "MEETING" and avg_score >= 80:
            disposition = DispositionOutcome.MEETING_READY
        elif avg_score >= 65:
            disposition = DispositionOutcome.QUALIFIED
        elif avg_score >= 50:
            disposition = DispositionOutcome.FOLLOWUP
        elif avg_score >= 35:
            disposition = DispositionOutcome.NURTURE
        else:
            disposition = DispositionOutcome.NO_FIT

        return {
            "engagement_score": round(engagement_score, 1),
            "pain_score": round(pain_score, 1),
            "intent_score": round(intent_score, 1),
            "authority_score": round(authority_score, 1),
            "urgency_score": round(urgency_score, 1),
            "next_step_score": round(next_step_score, 1),
            "overall_conversation_score": round(avg_score, 1),
            "disposition": disposition.value,
        }

    def format_dialer_display(
        self,
        opportunity: Dict[str, Any],
        conversation_state: ConversationState,
        memory: ConversationMemory,
        next_action: ConversationAction,
    ) -> str:
        """Render high-clarity dialer prompt panel for the human caller."""
        mode = self.determine_mode(opportunity)
        dm = opportunity.get("decision_maker", "Decision Maker")
        role = opportunity.get("role", "Owner")
        co = opportunity.get("company", "Target Company")
        pain = opportunity.get("pain", "Operations Bottleneck")
        evidence = opportunity.get("evidence", {}).get("claim") if isinstance(opportunity.get("evidence"), dict) else opportunity.get("why_this_company", "Active operations")

        return f"""================================================================================
MBM DYNAMIC CONVERSATION COPILOT
================================================================================
MODE:            {mode.value}
PROSPECT:        {dm} ({role}) — {co}
CURRENT STAGE:   {conversation_state.value}
IDENTITY STATE:  {memory.identity_state}
EVIDENCE:        {evidence}
PROSPECT PAIN:   {pain}

NEXT BEST MOVE:
[{next_action.action.value}] "{next_action.suggested_language}"

REASON:          {next_action.reason}
TRANSITION:      {next_action.state_transition}
CONFIDENCE:      {int(next_action.confidence * 100)}%
PREVIOUS TURNS:  {memory.engagement_turns} turns | Objections: {len(memory.objections)}
================================================================================"""
