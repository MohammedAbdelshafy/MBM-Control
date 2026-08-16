import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi.testclient import TestClient
from MBM.LeadEngine.gemini_agent_api import app, OBJECTION_PLAYBOOKS


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "service" in data


def test_objection_matrix_category(client):
    res = client.post("/api/objection", json={
        "objection": "We already have an answering service",
        "category": "ALREADY_HAVE_SOLUTION",
        "lead_name": "Dr. Sarah",
        "company": "Apex Clinic",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "PLAYBOOK_MATRIX"
    assert "auto-replies" in data["response"] or "autonomously" in data["response"]


def test_objection_all_12_categories(client):
    categories = [
        "PRICE", "TIMING", "TRUST", "AI_SKEPTICISM",
        "ALREADY_HAVE_SOLUTION", "DO_IT_INTERNALLY", "NO_NEED", "NO_BUDGET",
        "AUTHORITY", "SECURITY", "INTEGRATION", "STAFF",
    ]
    for cat in categories:
        res = client.post("/api/objection", json={
            "objection": f"Testing {cat}",
            "category": cat,
            "lead_name": "Test Prospect",
            "company": "Test Co",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "PLAYBOOK_MATRIX"
        assert len(data["response"]) > 10


def test_meeting_booking_and_brief_generation(client):
    res = client.post("/api/meeting", json={
        "lead_id": "TEST-LEAD-001",
        "company": "Summit Dental Group",
        "buyer": "Dr. John Summit",
        "role": "Owner & Lead Dentist",
        "date": "Tomorrow",
        "time": "10:30 AM",
        "offer": "24/7 AI Receptionist & Voice Agent",
        "pain": "Overdue patient recall backlog and missed calls",
        "why_agreed": "Agreed to 15-minute diagnostic demo",
        "phone": "+1-214-555-0199",
        "email": "drjohn@summitdental.com",
        "notes": "Interested in after-hours phone triage.",
        "expected_value_usd": 8400.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "MEETING_BOOKED"
    assert "brief_path" in data


def test_decision_recording_seller_and_buyer(client):
    # 1. Seller Warmed
    res_seller = client.post("/api/decision", json={
        "lead_id": "SELLER-001",
        "status": "Seller Warmed",
        "company": "123 Main St, Dallas, TX",
        "contact": "Bruce McLeod",
        "phone": "214-555-0101",
        "sales_lane": "REAL_ESTATE",
        "note": "Open to cash offer if closed in 14 days",
    })
    assert res_seller.status_code == 200
    assert res_seller.json()["ok"] is True

    # 2. AI Buyer Warmed
    res_buyer = client.post("/api/decision", json={
        "lead_id": "BUYER-001",
        "status": "AI Buyer Warmed",
        "company": "Apex Mechanical",
        "contact": "Marcus Vance",
        "phone": "214-555-0102",
        "sales_lane": "AI_CONSULTANCY",
        "note": "Wants to see automated scheduling demo",
    })
    assert res_buyer.status_code == 200
    assert res_buyer.json()["ok"] is True


def test_identity_transitions(client):
    # 1. Confirmed Owner
    res_owner = client.post("/api/identity", json={
        "lead_id": "DCAD-001",
        "contact_name": "Bruce McLeod",
        "phone": "214-555-0101",
        "company_or_property": "123 Main St, Dallas, TX",
        "claimed_role": "OWNER",
        "is_owner_confirmed": True,
    })
    assert res_owner.status_code == 200
    data_owner = res_owner.json()
    assert data_owner["ok"] is True
    assert data_owner["is_primary_eligible"] is True

    # 2. Wrong Person
    res_wrong = client.post("/api/identity", json={
        "lead_id": "DCAD-002",
        "contact_name": "Random Tenant",
        "phone": "214-555-0102",
        "company_or_property": "456 Oak St, Dallas, TX",
        "claimed_role": "WRONG_PERSON",
        "is_wrong_person": True,
    })
    assert res_wrong.status_code == 200
    data_wrong = res_wrong.json()
    assert data_wrong["ok"] is True
    assert data_wrong["is_primary_eligible"] is False


def test_session_scoreboard_flow(client):
    # GET
    res_get = client.get("/api/session-scoreboard")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "calls" in data_get
    assert "confirmed_revenue_usd" in data_get

    # POST update
    res_post = client.post("/api/session-scoreboard", json={
        "calls": 12,
        "connected": 8,
        "conversations": 6,
        "sellers_warmed": 3,
        "ai_buyers_warmed": 2,
        "qualified": 4,
        "meetings": 2,
        "proposals": 1,
        "deals": 1,
        "new_pipeline_usd": 24800.0,
        "confirmed_revenue_usd": 4000.0,
    })
    assert res_post.status_code == 200
    assert res_post.json()["ok"] is True
    assert res_post.json()["scoreboard"]["calls"] == 12
