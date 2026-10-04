"""WhatsApp AI Front Desk — pure conversation logic (no network, no side effects).

Stage machine:
    greet  -> qualify_name -> qualify_service -> qualify_urgency -> done
         -> faq (inline keyword answers at any stage)
         -> escalate

Public API:
    process_message(state, text) -> (new_state, reply_text, escalate: bool, stage: str)

State is a plain dict and can be JSON-serialized. Initial state for a new
sender is returned by new_session().
"""

ESCALATE_KEYWORDS = (
    "human", "agent", "real person", "real human", "call me", "phone",
    "talk to someone", "speak to someone", "live person",
)

FAQ_KEYWORDS = {
    "price": "Our pricing depends on the service. Can you tell me which service you need? I'll connect you with exact pricing.",
    "cost": "Our pricing depends on the service. Can you tell me which service you need? I'll connect you with exact pricing.",
    "how much": "Our pricing depends on the service. Can you tell me which service you need? I'll connect you with exact pricing.",
    "hours": "We're open Monday to Saturday, 9:00 to 18:00 local time. If you message outside those hours, leave your details and we'll call you first thing.",
    "location": "Please share your city or area and we'll direct you to the right team.",
    "open": "We're open Monday to Saturday, 9:00 to 18:00 local time.",
    "refund": "Refunds are handled case by case. I've noted your request — a team member will follow up with the policy details.",
    "appointment": "We can book you in. What day works best for you?",
    "book": "We can book you in. What day works best for you?",
}

SERVICES = ("cleaning", "consulting", "support", "sales", "booking", "other")


def new_session(sender: str) -> dict:
    """Return a fresh, JSON-serializable session state for a sender."""
    return {"sender": sender, "stage": "greet", "name": "", "service": "",
            "urgency": "", "failed_parses": 0}


def _escalate(state: dict, reason: str) -> tuple:
    state = dict(state)
    state["stage"] = "escalate"
    return state, (
        "No problem — I'm connecting you to a member of our team right now. "
        "They'll reply here shortly. (Reason noted: %s)" % reason
    ), True, "escalate"


def _faq_answer(text: str):
    lowered = text.lower()
    for key, answer in FAQ_KEYWORDS.items():
        if key in lowered:
            return answer
    return None


def _needs_escalation(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in ESCALATE_KEYWORDS)


def process_message(state: dict, text: str) -> tuple:
    """Run one inbound message through the state machine.

    Returns (new_state, reply_text, escalate: bool, stage: str).
    Pure function: never touches the network.
    """
    state = dict(state)
    stage = state.get("stage", "greet")
    text = (text or "").strip()

    # Escalation keywords work at ANY stage (before FAQ so a frustrated
    # "human please" wins over the faq check, which also matters for "call me").
    if _needs_escalation(text):
        return _escalate(state, "requested human assistance")

    if not text:
        return state, "I didn't catch that — could you repeat it?", False, stage

    if stage == "greet":
        state["stage"] = "qualify_name"
        return state, (
            "Hello! Thanks for reaching out. I'm the front desk assistant. "
            "What's your name?"
        ), False, "qualify_name"

    if stage == "qualify_name":
        name = text.split()[0].title() if text else ""
        state["name"] = name
        state["stage"] = "qualify_service"
        return state, (
            "Nice to meet you, %s. Which service are you interested in?\n"
            "Options: cleaning, consulting, support, sales, booking, or other."
            % (name or "there")
        ), False, "qualify_service"

    if stage == "qualify_service":
        faq = _faq_answer(text)
        lowered = text.lower()
        matched = next((s for s in SERVICES if s in lowered), None)
        if matched:
            state["service"] = matched
            state["stage"] = "qualify_urgency"
            return state, (
                "Got it — %s. How urgent is this? (today / this week / just browsing)"
                % matched
            ), False, "qualify_urgency"
        if faq:
            return state, faq, False, stage
        state["failed_parses"] = state.get("failed_parses", 0) + 1
        if state["failed_parses"] >= 2:
            return _escalate(state, "could not determine the service needed")
        return state, (
            "I want to make sure I send you to the right team. Could you pick "
            "one of: cleaning, consulting, support, sales, booking, or other?"
        ), False, stage

    if stage == "qualify_urgency":
        faq = _faq_answer(text)
        if faq:
            return state, faq, False, stage
        lowered = text.lower()
        if "today" in lowered or "urgent" in lowered or "asap" in lowered or "now" in lowered:
            urgency = "today"
        elif "week" in lowered:
            urgency = "this week"
        else:
            urgency = "low"
        state["urgency"] = urgency
        state["stage"] = "done"
        name = state.get("name") or "there"
        service = state.get("service") or "your request"
        return state, (
            "Thanks, %s! I've logged your request (%s, urgency: %s). "
            "A team member will follow up here shortly."
            % (name, service, urgency)
        ), False, "done"

    if stage == "done":
        faq = _faq_answer(text)
        if faq:
            return state, faq, False, stage
        return state, (
            "Your request is already with our team. Anything else I can help with? "
            "Say 'human' if you'd like to speak to someone directly."
        ), False, stage

    # Unknown stage -> safe reset
    state["stage"] = "greet"
    return state, "Hello! What's your name?", False, "greet"
