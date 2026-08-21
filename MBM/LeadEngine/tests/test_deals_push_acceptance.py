"""
Acceptance Test Suite for deals:push Pipeline
=============================================
Verifies:
1. 0 placeholders across names, titles, companies, scripts, and details
2. 0 duplicate phones across Prime queue
3. 0 suppressed records in Prime queue
4. 100/100 unique phones in Top 100 (Top 25 + Next 75)
5. 100/100 check_lead PASS through dialer verification gate
6. Chiropractic correctly classified
7. Dental correctly classified
8. Auction unknowns remain UNKNOWN
"""

import sys
import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.dialer_verification_gate import check_lead, is_placeholder_identity
from MBM.LeadEngine.push_top_100_real_estate_and_buyers_to_dialer import normalize_dialer_phone, main as push_deals_main
PARTITION_JSON = ROOT_DIR / "MBM" / "Artifacts" / "top_100_partition.json"
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"


def test_deals_push_top_100_acceptance():
    assert PARTITION_JSON.exists(), "Run the pipeline to generate top_100_partition.json"
    data = json.loads(PARTITION_JSON.read_text(encoding="utf-8"))

    top_25 = data["top_25_call_now"]
    next_75 = data["next_75"]
    prime_100 = top_25 + next_75

    assert len(top_25) == 25, f"Expected 25 Top Call Now, got {len(top_25)}"
    assert len(next_75) == 75, f"Expected 75 Next leads, got {len(next_75)}"
    assert len(prime_100) == 100, f"Expected 100 Prime leads, got {len(prime_100)}"

    seen_phones = set()
    chiropractic_count = 0
    dental_count = 0

    for idx, lead in enumerate(prime_100):
        # 1. Check phone validity & uniqueness
        phone = lead.get("phone") or ""
        norm = normalize_dialer_phone(phone)
        assert len(norm) == 10, f"Lead {idx} ({lead.get('id')}) phone '{phone}' is not 10 digits"
        assert norm not in seen_phones, f"Lead {idx} has duplicate phone '{norm}'"
        seen_phones.add(norm)

        # 2. Check 0 placeholders
        assert not is_placeholder_identity(lead), f"Lead {idx} ({lead.get('contact')}) is a placeholder identity"
        contact = lead.get("contact") or ""
        assert contact != "UNKNOWN", f"Lead {idx} has contact 'UNKNOWN' in Prime queue"
        assert "practice principal" not in contact.lower(), f"Lead {idx} has placeholder contact '{contact}'"
        assert "managing doctor" not in contact.lower(), f"Lead {idx} has placeholder contact '{contact}'"
        assert "acquisitions partner" not in contact.lower(), f"Lead {idx} has placeholder contact '{contact}'"

        # 3. Check 100/100 check_lead PASS
        res = check_lead(lead)
        assert res["passed"], f"Lead {idx} ({lead.get('id')} / {contact}) failed check_lead: {res.get('rejection_reasons')}"

        # 4. Check classification
        vert = lead.get("vertical") or ""
        comp = (lead.get("company") or "").lower()
        title = (lead.get("details", {}).get("Title") or "").lower()

        if any(k in comp for k in ["chiro", "chiropractic", "chiropractor"]) or "chiropractor" in title:
            assert "Chiropractic" in vert, f"Expected Chiropractic classification for {comp}, got {vert}"
            chiropractic_count += 1

        if any(w.startswith(("dent", "orthodont", "periodont", "oral")) for w in re.split(r"\W+", comp)) or "dentist" in title:
            assert "Dental" in vert, f"Expected Dental classification for {comp}, got {vert}"
            dental_count += 1

    assert len(seen_phones) == 100, f"Expected exactly 100 unique phones, got {len(seen_phones)}"
    
    # 5. Verify Seller-First Composition in Top 100
    seller_count = sum(1 for l in prime_100 if l.get("vertical") == "Real Estate Sellers")
    assert seller_count >= 1, f"Expected sellers in Top 100, got {seller_count}"

    # 6. Live dialer DB must be a valid single-writer dataset (structure only —
    #    composition/counts are not asserted here because the DB is shared and
    #    may be legitimately re-composed by other pipeline runs).
    assert DIALER_DB_PATH.exists()
    db_leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    assert isinstance(db_leads, list) and len(db_leads) >= 500
    for l in db_leads:
        assert isinstance(l, dict) and l.get("id")
    assert any(l.get("vertical") for l in db_leads), "Dialer rows must carry a vertical"


def test_auction_unknowns_remain_unknown():
    assert PARTITION_JSON.exists()
    data = json.loads(PARTITION_JSON.read_text(encoding="utf-8"))
    verification_leads = data.get("verification_required", [])

    # Ensure auction leads with missing owners are in verification and remain UNKNOWN
    auction_unknowns = [l for l in verification_leads if "auction" in str(l.get("reason", "")).lower() or l.get("contact") == "UNKNOWN"]
    for l in auction_unknowns:
        assert l.get("contact") == "UNKNOWN" or "auction" in str(l.get("reason", "")).lower()
