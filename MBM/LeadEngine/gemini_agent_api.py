import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from MBM.LeadEngine.gtm_quick_brief import (
    GtmMeetingCenter,
    GtmEmailCenter,
    GTM_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    MEETINGS_DIR,
)
from MBM.LeadEngine.gtm_notification_bus import (
    NotificationBus,
    NotificationRecord,
    NotificationKind,
    PriorityLevel,
    DeliveryStatus,
)
from MBM.LeadEngine.owner_identity import (
    IdentityState,
    evaluate_lead_identity,
    is_primary_eligible,
)

app = FastAPI(title="MBM Tonight Calling & GTM Revenue Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMMENTS_FILE = Path(__file__).resolve().parent / "dialer_comments.json"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        pass

gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        pass

# Initialize centers and buses
meeting_center = GtmMeetingCenter(MEETINGS_DIR / "index.json", MEETINGS_DIR)
notification_bus = NotificationBus()

SCOREBOARD_PATH = GTM_ARTIFACTS_DIR / "tonight_scoreboard.json"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ObjectionRequest(BaseModel):
    objection: str
    category: Optional[str] = None
    script: str = "Standard cold call pitch"
    lead_name: str = "Prospect"
    company: str = "Company"
    vertical: Optional[str] = None


class MeetingRequest(BaseModel):
    lead_id: str
    company: str
    buyer: str
    role: Optional[str] = "Decision Maker"
    date: str
    time: Optional[str] = "10:30 AM"
    offer: Optional[str] = "24/7 AI Receptionist & Voice Agent"
    pain: Optional[str] = "Operational time loss and lead follow-up delays"
    why_agreed: Optional[str] = "Agreed to 15-minute diagnostic demo"
    phone: Optional[str] = ""
    email: Optional[str] = ""
    notes: Optional[str] = ""
    expected_value_usd: Optional[float] = 8400.0


class DecisionRequest(BaseModel):
    lead_id: str
    status: str
    contact: Optional[str] = ""
    company: Optional[str] = ""
    vertical: Optional[str] = ""
    phone: Optional[str] = ""
    amount: Optional[str] = ""
    note: Optional[str] = ""
    follow_up: Optional[str] = ""
    sales_lane: Optional[str] = "AI_CONSULTANCY"


class IdentityRequest(BaseModel):
    lead_id: str
    contact_name: str
    phone: str
    company_or_property: str
    claimed_role: str
    is_owner_confirmed: bool = False
    is_authorized_decision_maker: bool = False
    is_wrong_person: bool = False
    is_wrong_number: bool = False
    is_tenant: bool = False


class ScoreboardState(BaseModel):
    calls: int = 0
    connected: int = 0
    conversations: int = 0
    sellers_warmed: int = 0
    ai_buyers_warmed: int = 0
    qualified: int = 0
    meetings: int = 0
    proposals: int = 0
    deals: int = 0
    new_pipeline_usd: float = 0.0
    confirmed_revenue_usd: float = 0.0
    session_start: Optional[str] = None
    last_updated: Optional[str] = None


# ---------------------------------------------------------------------------
# Objection Playbook Matrix
# ---------------------------------------------------------------------------

OBJECTION_PLAYBOOKS = {
    "PRICE": "Our growth pilot is completely risk-reversed — you don't pay a cent until after onboarding when you see the live agent working in your workflow. Sound fair to take a look?",
    "TIMING": "Totally understand. That's why we take only 15 minutes to diagnose if there's real ROI before you commit any time. Would tomorrow morning or afternoon be better?",
    "TRUST": "We don't sell generic chatbot subscriptions. We build and integrate custom autonomous agents directly into your existing phone lines and CRM. Can I show you a 60-second live sample?",
    "AI_SKEPTICISM": "Our voice models operate at sub-second conversational latency with human cadence. Most callers never realize it's AI until told. Let's test it on a test call tomorrow.",
    "ALREADY_HAVE_SOLUTION": "Most existing systems only send simple text auto-replies. Our agents actively qualify, handle objections, and schedule calendar slots autonomously. What tool are you currently using?",
    "DO_IT_INTERNALLY": "Internal development usually takes 4-6 months and $40k+ in engineering payroll. We deploy pre-trained, production-ready workflows in 48 hours.",
    "NO_NEED": "If your team already captures 100% of calls and follows up in under 60 seconds 24/7, you might be set. Are any weekend or after-hours inquiries ever delayed?",
    "NO_BUDGET": "This isn't an expense line — if an AI receptionist captures just 2 lost clients per month, it generates 5x its cost. What does a typical new client bring in for you?",
    "AUTHORITY": "I completely understand. I'd love to include your partner on a quick 15-minute walkthrough so you can both see the live demo. What's their email address?",
    "SECURITY": "All data stays within encrypted, SOC2/HIPAA compliant pipelines with zero model training on your private client records.",
    "INTEGRATION": "We connect directly via native APIs and webhooks to your existing CRM, EHR, and phone lines with zero downtime or workflow disruption.",
    "STAFF": "This doesn't replace your team — it frees them from repetitive phone triage so they can focus on high-touch client work.",
}


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "service": "MBM Tonight Calling & GTM Revenue API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "groq": bool(groq_client),
        "gemini": bool(gemini_client),
        "nvidia": bool(NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("nvapi-demo")),
    }


@app.post("/api/objection")
async def handle_objection(req: ObjectionRequest):
    obj_upper = (req.category or "").upper()
    if obj_upper in OBJECTION_PLAYBOOKS:
        return {"response": OBJECTION_PLAYBOOKS[obj_upper], "source": "PLAYBOOK_MATRIX"}

    prompt = f"""
    You are an elite, high-ticket cold calling sales closer (Jordan Belfort + Chris Voss caliber).
    You are on a live phone call with prospect {req.lead_name} from {req.company}.
    Vertical: {req.vertical or "Business"}
    Current pitch: "{req.script}"
    Prospect objection: "{req.objection}"

    Give me the EXACT, 1-2 sentence conversational response to say out loud right now to overcome this objection, pattern-interrupt them, and secure the next micro-commitment.
    NO fluff, NO greetings, NO quotation marks. Just the exact conversational words to speak.
    """

    # 1. Try Groq LPU (Sub-second latency)
    if groq_client:
        try:
            chat = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a master cold calling tele-closer. Output only the exact words to say."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=150
            )
            return {"response": chat.choices[0].message.content.strip().strip('"'), "source": "GROQ_LPU"}
        except Exception as ge:
            print(f"[WARN] Groq error: {ge}")

    # 2. Try NVIDIA NIM
    if NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("nvapi-demo"):
        try:
            import urllib.request
            payload = {
                "model": "meta/llama-3.3-70b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a master cold calling tele-closer. Output only the exact words to say."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 150
            }
            req_nv = urllib.request.Request(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_nv, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"response": data["choices"][0]["message"]["content"].strip().strip('"'), "source": "NVIDIA_NIM"}
        except Exception as nve:
            print(f"[WARN] NVIDIA NIM error: {nve}")

    # 3. Try Gemini
    if gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return {"response": response.text.strip().strip('"'), "source": "GEMINI"}
        except Exception as gme:
            print(f"[WARN] Gemini error: {gme}")

    # 4. Fallback to matched playbook or heuristic
    obj_lower = req.objection.lower()
    for cat, script in OBJECTION_PLAYBOOKS.items():
        if cat.lower().replace("_", " ") in obj_lower:
            return {"response": script, "source": "FALLBACK_MATRIX"}

    if "not interested" in obj_lower or "not selling" in obj_lower:
        return {"response": f"Totally understand {req.lead_name}. Are you holding onto it long term, or is there a specific number where letting it go would make sense?", "source": "HEURISTIC"}
    elif "price" in obj_lower or "cost" in obj_lower or "how much" in obj_lower:
        return {"response": "Our growth retainer is $1,997/mo, but you pay zero until after onboarding when you see the live agent working. Sound fair to take a 15-minute look?", "source": "HEURISTIC"}
    elif "email" in obj_lower or "send info" in obj_lower:
        return {"response": f"I'd be glad to send a 1-page overview! What's the best email for you? If the numbers look good, could we do a quick 10-minute walkthrough this Thursday?", "source": "HEURISTIC"}

    return {"response": f"I completely understand {req.lead_name}. If I could show you how this saves 10+ hours a week with zero technical effort, would you be open to a 30-second summary?", "source": "DEFAULT"}


@app.post("/api/meeting")
async def create_meeting(req: MeetingRequest):
    """Book a meeting, generate the executive meeting brief, and notify GTM channels."""
    meeting_payload = {
        "id": req.lead_id,
        "company": req.company,
        "buyer": req.buyer,
        "role": req.role or "Decision Maker",
        "date": req.date,
        "time": req.time or "10:30 AM",
        "ai_fit": req.offer or "AI Assistant Retainer",
        "offer": req.offer or "AI Assistant Retainer",
        "pain": req.pain or "Operational time loss",
        "why_agreed": req.why_agreed or "Agreed to 15-minute diagnostic demo",
        "phone": req.phone or "",
        "email": req.email or "",
        "notes": req.notes or "",
        "expected_value_usd": req.expected_value_usd or 8400.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Upsert into MeetingCenter (creates JSON and MD files in Artifacts/GTM/meetings/)
    meeting_center.upsert(meeting_payload)

    # 2. Write rich meeting brief markdown
    brief_filename = f"meeting_brief_{req.company.lower().replace(' ', '_').replace('&', 'and')[:40]}.md"
    brief_path = MEETINGS_DIR / brief_filename
    brief_content = f"""# Executive Discovery & Meeting Brief: {req.company}

**Company:** {req.company}  
**Buyer / Decision Maker:** {req.buyer} ({req.role})  
**Date & Time:** {req.date} at {req.time}  
**Phone:** {req.phone}  
**Email:** {req.email}  

---

## 🎯 Strategic Summary
- **Observed Problem / Pain:** {req.pain}  
- **Why Now / Why Agreed:** {req.why_agreed}  
- **Recommended Assistant Package:** {req.offer}  
- **Expected Deal Value:** ${req.expected_value_usd:,.2f}  

## 🧠 Discovery & Conversation Notes
{req.notes or "Scheduled during live calling session."}

## 📋 Recommended Demo Agenda (15 Minutes)
1. **Minute 0–3:** Validate current front-desk / workflow bottleneck.
2. **Minute 4–8:** Live interactive call test with the tailored {req.offer}.
3. **Minute 9–12:** Review CRM integration & Neteller Retainer SOW.
4. **Minute 13–15:** Confirm onboarding kickoff & payment.
"""
    brief_path.write_text(brief_content, encoding="utf-8")

    # 3. Publish to Notification Bus
    notification_bus.publish(
        kind=NotificationKind.MEETING_BOOKED,
        delivery_key=NotificationBus.meeting_key(req.lead_id),
        payload=meeting_payload,
    )

    return {
        "ok": True,
        "meeting": meeting_payload,
        "brief_path": str(brief_path),
        "status": "MEETING_BOOKED",
    }


@app.post("/api/decision")
async def record_decision(req: DecisionRequest):
    """Record a post-call decision with live GTM state synchronization."""
    status_upper = req.status.upper().replace(" ", "_")

    payload = {
        "lead_id": req.lead_id,
        "status": req.status,
        "company": req.company,
        "contact": req.contact,
        "phone": req.phone,
        "amount": req.amount,
        "note": req.note,
        "follow_up": req.follow_up,
        "sales_lane": req.sales_lane,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    # Route meaningful events
    if "WARM" in status_upper or "HOT_LEAD" in status_upper:
        notification_bus.publish(
            kind=NotificationKind.LEAD_WARMED,
            delivery_key=f"lead_warmed_{req.lead_id}_{int(datetime.now(timezone.utc).timestamp())}",
            payload={
                "company": req.company,
                "buyer": req.contact,
                "offer": "AI Assistant Retainer" if req.sales_lane == "AI_CONSULTANCY" else "Cash Acquisition Offer",
                "signal": req.note or f"Expressed interest during call ({req.status})",
                "sales_lane": req.sales_lane,
            },
        )
    elif "DEAL_WON" in status_upper or "CASH_OFFER_MADE" in status_upper:
        notification_bus.publish(
            kind=NotificationKind.DEAL_WON,
            delivery_key=NotificationBus.deal_won_key(req.lead_id),
            payload={
                "company": req.company,
                "offer": "AI Assistant Retainer" if req.sales_lane == "AI_CONSULTANCY" else "Cash Acquisition Offer",
                "value": req.amount or "$4,000/mo ($48,000 ARR)",
                "revenue_state": "CONFIRMED (Neteller)",
                "next_step": "Onboarding kickoff & client setup",
            },
        )
    elif "PROPOSAL" in status_upper:
        notification_bus.publish(
            kind=NotificationKind.PROPOSAL_SENT,
            delivery_key=f"proposal_{req.lead_id}_{int(datetime.now(timezone.utc).timestamp())}",
            payload={
                "company": req.company,
                "offer": "AI Assistant Retainer",
                "value": req.amount or "$3,500/mo ($42,000 ARR)",
                "status": "Awaiting decision",
            },
        )

    # Persist decision to dialer_comments.json for daily refresh processing
    try:
        comments: list = []
        if COMMENTS_FILE.exists():
            comments = json.loads(COMMENTS_FILE.read_text(encoding="utf-8"))
        comments.append(payload)
        COMMENTS_FILE.write_text(json.dumps(comments, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass

    return {"ok": True, "status": req.status, "lead_id": req.lead_id}


@app.post("/api/identity")
async def update_identity(req: IdentityRequest):
    """Record live caller identity confirmation and apply suppression rules."""
    lead_dict = {
        "id": req.lead_id,
        "contact": req.contact_name,
        "phone": req.phone,
        "company": req.company_or_property,
    }

    rel = req.claimed_role
    if req.is_owner_confirmed:
        rel = "OWNER"
    elif req.is_authorized_decision_maker:
        rel = "AUTHORIZED_DECISION_MAKER"
    elif req.is_wrong_person:
        rel = "WRONG_PERSON"
    elif req.is_tenant:
        rel = "TENANT"

    eval_result = evaluate_lead_identity(
        lead_dict,
        caller_name=req.contact_name,
        relationship=rel,
        property_confirmed=req.is_owner_confirmed or req.is_authorized_decision_maker,
        name_confirmed=req.is_owner_confirmed,
        wrong_number=req.is_wrong_number,
    )

    return {
        "ok": True,
        "lead_id": req.lead_id,
        "state": eval_result.state.value if hasattr(eval_result.state, "value") else str(eval_result.state),
        "score": eval_result.score,
        "is_primary_eligible": is_primary_eligible(eval_result.state),
        "evidence_used": eval_result.evidence_used,
    }


@app.get("/api/session-scoreboard")
async def get_scoreboard():
    """Retrieve Tonight calling session scoreboard."""
    if SCOREBOARD_PATH.exists():
        try:
            data = json.loads(SCOREBOARD_PATH.read_text(encoding="utf-8"))
            return data
        except Exception:
            pass

    default_sb = ScoreboardState(
        session_start=datetime.now(timezone.utc).isoformat(),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
    return default_sb.dict()


@app.post("/api/session-scoreboard")
async def update_scoreboard(sb: ScoreboardState):
    """Save Tonight calling session scoreboard."""
    SCOREBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    sb.last_updated = datetime.now(timezone.utc).isoformat()
    SCOREBOARD_PATH.write_text(json.dumps(sb.dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "scoreboard": sb.dict()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3005)

