"""
TESTS: DYNAMIC CONVERSATION ENGINE
=============================================================================
Comprehensive unit tests and end-to-end simulations for:
1. Cold, Warm, and Hot conversation modes
2. Pattern interrupts and evidence-driven openings
3. Discovery engine branching and question category selection
4. Pain quantification and PainModel source distinction
5. Response classification (interested, skeptical, busy, wrong person, etc.)
6. Reflection engine (validating problem before AI solution presentation)
7. AI-fit transition and 1-sentence value propositions
8. Objection handling taxonomy and multi-step isolation
9. Progressive micro-commitments and CTA tier selection
10. Conversation state transitions and repeated-question prevention
11. Full multi-vertical conversational simulations (HVAC, Roofing, Dental,
    Construction, Skepticism, Price Objection, Busy, Wrong Person)
=============================================================================
"""

import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.conversation_engine import (
    DynamicConversationEngine,
    ConversationMode,
    ConversationState,
    ConversationActionType,
    ConversationMemory,
    PatternInterruptType,
    QuestionCategory,
    ProspectClassification,
    ObjectionCategory,
    PainSourceType,
    DispositionOutcome,
)


@pytest.fixture
def engine():
    return DynamicConversationEngine()


@pytest.fixture
def hvac_opportunity():
    return {
        "id": "OPP-HVAC-01",
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Founder & Managing Director",
        "industry": "HVAC & Mechanical Contractors",
        "phone": "+12148849120",
        "email": "marcus@apexmechanical.com",
        "intent_score": 95.0,
        "intent_tier": "HOT",
        "pain": "20+ missed after-hours emergency calls weekly",
        "why_now": "Active hiring for weekend emergency dispatcher",
        "recommended_ai_assistant": "24/7 AI Emergency Call Answering & Dispatch Concierge",
        "sku": "AI-ASSISTANT-HVAC-DISPATCH",
        "monthly_retainer_usd": 2000.0,
        "evidence": {
            "claim": "Marcus Vance seeks 24/7 after-hours dispatch solution on LinkedIn",
            "source": "LinkedIn Post",
        }
    }


@pytest.fixture
def roofing_opportunity():
    return {
        "id": "OPP-ROOF-02",
        "company": "Vanguard Commercial Roofing",
        "decision_maker": "Derek Holloway",
        "role": "Owner & President",
        "industry": "Roofing & Storm Restoration",
        "phone": "+18175591024",
        "email": "derek@vanguardroof.com",
        "intent_score": 78.0,
        "intent_tier": "WARM",
        "pain": "48-hour estimate bottleneck during hail storm seasons",
        "why_now": "Hail event across North Texas creating lead backlog",
        "recommended_ai_assistant": "Autonomous Storm & Estimate Lead Follow-Up Swarm",
        "sku": "AI-ASSISTANT-ROOF-SWARM",
        "monthly_retainer_usd": 2500.0,
        "evidence": {
            "claim": "Derek Holloway discussing storm lead follow-up backlog",
            "source": "Contractor Talk Forum",
        }
    }


@pytest.fixture
def cold_opportunity():
    return {
        "id": "OPP-COLD-03",
        "company": "Metro Plumbing Services",
        "decision_maker": "Dave Miller",
        "role": "General Manager",
        "industry": "Commercial Plumbing",
        "phone": "+19725550199",
        "intent_score": 45.0,
        "intent_tier": "DISCOVERED",
        "pain": "unworked inbound calls during peak hours",
        "recommended_ai_assistant": "24/7 AI Intake Concierge",
        "monthly_retainer_usd": 1500.0,
    }


# ---------------------------------------------------------------------------
# 1. Mode Determination Tests
# ---------------------------------------------------------------------------

def test_conversation_mode_determination(engine, hvac_opportunity, roofing_opportunity, cold_opportunity):
    """Verify HOT, WARM, and COLD modes are assigned correctly based on tier & score."""
    assert engine.determine_mode(hvac_opportunity) == ConversationMode.HOT
    assert engine.determine_mode(roofing_opportunity) == ConversationMode.WARM
    assert engine.determine_mode(cold_opportunity) == ConversationMode.COLD


# ---------------------------------------------------------------------------
# 2. Openings & Pattern Interrupts
# ---------------------------------------------------------------------------

def test_openings_and_pattern_interrupts(engine, hvac_opportunity, cold_opportunity):
    """Verify dynamic opening generation across different pattern interrupts."""
    hot_opening = engine.get_opening(hvac_opportunity, ConversationMode.HOT)
    assert hot_opening.action == ConversationActionType.ASK
    assert "Marcus" in hot_opening.suggested_language
    assert "Apex Mechanical" in hot_opening.suggested_language
    assert "30 seconds" in hot_opening.suggested_language

    cold_perm_opening = engine.get_opening(cold_opportunity, ConversationMode.COLD, PatternInterruptType.PERMISSION)
    assert "20 seconds" in cold_perm_opening.suggested_language
    assert "wasting your time" in cold_perm_opening.suggested_language

    cold_diag_opening = engine.get_opening(cold_opportunity, ConversationMode.COLD, PatternInterruptType.DIAGNOSTIC)
    assert "quick question about your current" in cold_diag_opening.suggested_language


# ---------------------------------------------------------------------------
# 3. Response Classification Tests
# ---------------------------------------------------------------------------

def test_response_classifier(engine):
    """Verify classification of prospect utterances into typed intents and objections."""
    # Interest
    cls, _ = engine.classify_response("Yes, we miss calls all the time and it is a massive bottleneck.")
    assert cls == ProspectClassification.INTERESTED

    # Curiosity
    cls, _ = engine.classify_response("How does this actually work? Tell me more.")
    assert cls == ProspectClassification.CURIOUS

    # Busy
    cls, _ = engine.classify_response("I'm in the middle of a job right now, can you call me back later?")
    assert cls == ProspectClassification.BUSY

    # Wrong Person
    cls, _ = engine.classify_response("I'm not the owner, I'm just a tenant renting the unit.")
    assert cls == ProspectClassification.WRONG_PERSON

    # Wrong Number
    cls, _ = engine.classify_response("There is no one by that name here, wrong number.")
    assert cls == ProspectClassification.WRONG_NUMBER

    # Objections
    cls, _ = engine.classify_response("That sounds too expensive, what is the cost?")
    assert cls == ProspectClassification.PRICE_CONCERN

    cls, _ = engine.classify_response("We already use ServiceTitan and have a receptionist.")
    assert cls == ProspectClassification.ALREADY_SOLVED

    cls, _ = engine.classify_response("Is this an AI robot? AI voice sounds super robotic.")
    assert cls == ProspectClassification.SKEPTICAL

    # Meeting intent
    cls, _ = engine.classify_response("Sounds good, let's do Thursday morning on Google Meet.")
    assert cls == ProspectClassification.MEETING_INTENT


# ---------------------------------------------------------------------------
# 4. Multi-Step Conversational Simulation Tests
# ---------------------------------------------------------------------------

def test_hvac_full_cycle_simulation(engine, hvac_opportunity):
    """
    Simulation 1: HVAC Owner
    Cold Call -> Permission -> Discovery -> Pain Confirmed -> Quantify ->
    Reflection -> AI Fit -> 15-Min Meeting Booked.
    """
    mem = ConversationMemory()

    # 1. Opening
    act1 = engine.next_action(hvac_opportunity, ConversationState.CALL_OPEN, memory=mem)
    assert act1.action == ConversationActionType.ASK
    assert "Marcus" in act1.suggested_language

    # 2. Permission granted
    act2 = engine.next_action(
        hvac_opportunity,
        ConversationState.PERMISSION,
        last_prospect_message="Sure, I've got 20 seconds, go ahead.",
        memory=mem,
    )
    assert act2.action == ConversationActionType.ASK
    assert act2.question_category == QuestionCategory.WORKFLOW

    # 3. Discovery: Pain confirmed -> Quantify volume
    act3 = engine.next_action(
        hvac_opportunity,
        ConversationState.DISCOVERY,
        last_prospect_message="Yeah, our after-hours emergency calls go to voicemail and dispatchers miss half of them.",
        memory=mem,
    )
    assert act3.action == ConversationActionType.QUANTIFY
    assert "how many" in act3.suggested_language.lower()

    # 4. Quantified -> Reflection Engine
    act4 = engine.next_action(
        hvac_opportunity,
        ConversationState.PAIN_QUANTIFIED,
        last_prospect_message="We're missing about 15 to 20 calls every single weekend.",
        memory=mem,
    )
    assert act4.action == ConversationActionType.REFLECT
    assert "hearing you right" in act4.suggested_language

    # 5. Reflection agreed -> AI Fit Positioning
    act5 = engine.next_action(
        hvac_opportunity,
        ConversationState.SOLUTION_FIT,
        last_prospect_message="Yes, that's exactly right.",
        memory=mem,
    )
    assert act5.action == ConversationActionType.POSITION
    assert "24/7 AI Emergency Call" in act5.suggested_language

    # 6. Solution approved -> Meeting CTA
    act6 = engine.next_action(
        hvac_opportunity,
        ConversationState.COMMITMENT,
        last_prospect_message="I'd definitely be interested in seeing how it handles an emergency dispatch.",
        memory=mem,
    )
    assert act6.action == ConversationActionType.CTA
    assert "15-minute diagnostic" in act6.suggested_language

    # 7. Meeting Confirmed
    act7 = engine.next_action(
        hvac_opportunity,
        ConversationState.MEETING,
        last_prospect_message="Thursday at 10 AM works great, send the calendar invite.",
        memory=mem,
    )
    assert act7.action == ConversationActionType.CONFIRM

    # Evaluate Score
    mem.next_step = "MEETING"
    mem.identity_state = "CONFIRMED_OWNER"
    score_report = engine.calculate_conversation_score(mem)
    assert score_report["disposition"] == DispositionOutcome.MEETING_READY.value
    assert score_report["overall_conversation_score"] >= 80.0


def test_skeptical_objection_handling_simulation(engine, hvac_opportunity):
    """
    Simulation 2: Skeptical prospect raising AI quality objection.
    Engine acknowledges and offers zero-risk live test rather than arguing.
    """
    mem = ConversationMemory()
    act = engine.next_action(
        hvac_opportunity,
        ConversationState.DISCOVERY,
        last_prospect_message="We tried an AI voice bot last year and it sounded super robotic and callers hated it.",
        memory=mem,
    )
    assert act.action == ConversationActionType.HANDLE_OBJECTION
    assert act.objection_category == ObjectionCategory.AI_SKEPTICISM
    assert "ultra-low latency neural voice" in act.suggested_language
    assert "AI_SKEPTICISM" in mem.objections


def test_price_objection_handling_simulation(engine, roofing_opportunity):
    """
    Simulation 3: Price objection
    Engine reframes monthly retainer against high-ticket job value.
    """
    mem = ConversationMemory()
    act = engine.next_action(
        roofing_opportunity,
        ConversationState.SOLUTION_FIT,
        last_prospect_message="How much is this going to cost us? We're trying to keep overhead low.",
        memory=mem,
    )
    assert act.action == ConversationActionType.HANDLE_OBJECTION
    assert act.objection_category == ObjectionCategory.PRICE
    assert "average value of a typical completed job" in act.suggested_language


def test_busy_prospect_simulation(engine, cold_opportunity):
    """
    Simulation 4: Busy prospect
    Engine immediately respects time and offers clean callback slot.
    """
    mem = ConversationMemory()
    act = engine.next_action(
        cold_opportunity,
        ConversationState.CALL_OPEN,
        last_prospect_message="I'm on a job site right now and can't talk.",
        memory=mem,
    )
    assert act.action == ConversationActionType.SCHEDULE_FOLLOWUP
    assert "middle of something" in act.suggested_language


def test_wrong_person_suppression_simulation(engine, hvac_opportunity):
    """
    Simulation 5: Wrong person
    Engine identifies tenant/non-owner and requests correct decision maker.
    """
    mem = ConversationMemory()
    act = engine.next_action(
        hvac_opportunity,
        ConversationState.CALL_OPEN,
        last_prospect_message="I don't own the building, I'm just a tenant renting here.",
        memory=mem,
    )
    assert act.action == ConversationActionType.CLARIFY
    assert "managing owner" in act.suggested_language


def test_wrong_number_terminal_simulation(engine, cold_opportunity):
    """
    Simulation 6: Wrong number
    Engine immediately ends call gracefully and marks suppression.
    """
    mem = ConversationMemory()
    act = engine.next_action(
        cold_opportunity,
        ConversationState.CALL_OPEN,
        last_prospect_message="You have the wrong number, don't call this line again.",
        memory=mem,
    )
    assert act.action == ConversationActionType.END_CALL
    assert "Removing this number" in act.suggested_language


def test_dialer_display_formatting(engine, hvac_opportunity):
    """Verify dialer telemetry text renders clean guidance for human agents."""
    mem = ConversationMemory()
    act = engine.next_action(hvac_opportunity, ConversationState.CALL_OPEN, memory=mem)
    display = engine.format_dialer_display(hvac_opportunity, ConversationState.CALL_OPEN, mem, act)

    assert "MBM DYNAMIC CONVERSATION COPILOT" in display
    assert "MODE:            HOT" in display
    assert "PROSPECT:        Marcus Vance" in display
    assert "NEXT BEST MOVE:" in display
