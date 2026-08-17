import sys
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter
from MBM.LeadEngine.offer_architect import get_offer_architect, OfferArchitect

def test_single_writer_lock_atomic_protection(tmp_path):
    target_db = tmp_path / "leads_database.json"
    initial_leads = [
        {"id": "L1", "company": "Test Co 1", "phone": "+12145550100"},
        {"id": "L2", "company": "Test Co 2", "phone": "+12145550200"},
    ]
    target_db.write_text(json.dumps(initial_leads), encoding="utf-8")

    writer = DialerSingleWriter(db_path=target_db)

    # Adding a new lead
    new_leads = [
        {"id": "L3", "company": "Test Co 3", "phone": "+12145550300"},
    ]
    res = writer.commit_update(new_leads, author="TEST_WRITER")
    assert res["ok"] is True
    assert res["final_count"] == 3

    # Updating single lead does not shrink dataset
    updated_lead = [{"id": "L1", "company": "Test Co 1 Updated", "phone": "+12145550100"}]
    res2 = writer.commit_update(updated_lead, author="TEST_UPDATER")
    assert res2["ok"] is True
    assert res2["final_count"] == 3

    stored = json.loads(target_db.read_text(encoding="utf-8"))
    assert len(stored) == 3
    l1 = next(l for l in stored if l["id"] == "L1")
    assert l1["company"] == "Test Co 1 Updated"


def test_offer_architect_niche_packaging():
    architect = get_offer_architect()
    assert isinstance(architect, OfferArchitect)

    strategy = architect.build_sales_strategy_for_lead({
        "id": "LEAD-NPI-TEST",
        "company": "Advantage Dental Partners",
        "decision_maker": "Dr. Sarah Adams",
        "role": "Managing Partner",
        "industry": "Dental Practice",
        "phone": "+12145550199",
        "city": "Dallas",
        "state": "TX",
    })

    assert strategy["company"] == "Advantage Dental Partners"
    assert "offer" in strategy
    assert "conversation_script" in strategy
    assert len(strategy["conversation_script"]["objection_playbook"]) >= 12
    assert "PRICE" in strategy["conversation_script"]["objection_playbook"]
    assert "STAFF" in strategy["conversation_script"]["objection_playbook"]


def test_leads_database_contract_integrity():
    db_path = Path("mbm-dialer/app/public/leads_database.json")
    assert db_path.exists()

    leads = json.loads(db_path.read_text(encoding="utf-8"))
    assert len(leads) >= 880

    new_today = [l for l in leads if l.get("new_today") or l.get("first_seen_at") == "2026-08-16"]
    assert len(new_today) >= 100

    # Ensure all new_today leads have real source provenance
    for lead in new_today:
        assert lead.get("source") in [
            "US Government CMS NPI Registry",
            "Dallas County Appraisal District (DCAD)",
            "Authoritative Public Business Directory",
        ] or "NPI" in str(lead.get("source", ""))
        assert len(lead.get("phone", "")) >= 10
        assert not str(lead.get("phone")).startswith("+1200")
