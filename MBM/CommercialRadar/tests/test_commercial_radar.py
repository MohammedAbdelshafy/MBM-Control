import pytest
from datetime import datetime, timedelta, timezone
from MBM.CommercialRadar.candidate import PainCandidate, Event
from MBM.CommercialRadar.scoring import EvidenceScoring

def test_pain_candidate_maturity_derivation():
    candidate = PainCandidate(
        candidate_id="c_1",
        pain_family="operational_friction",
        description="Too much manual data entry",
        target_market="SMB",
        discovered_at=datetime.now(timezone.utc).isoformat(),
        independence_key="source_x"
    )
    assert candidate.state == "candidate"
    
    # Appending a demo books moves state to validated
    candidate.append_event(Event("e_1", "demo_booked", datetime.now(timezone.utc).isoformat()))
    assert candidate.state == "validated"
    
    # Appending a payment moves state to winner
    candidate.append_event(Event("e_2", "payment", datetime.now(timezone.utc).isoformat()))
    assert candidate.state == "winner"
    
    # Appending a refund moves state to rejected
    candidate.append_event(Event("e_3", "refund", datetime.now(timezone.utc).isoformat()))
    assert candidate.state == "rejected"

def test_scoring_determinism_and_cap():
    candidate = PainCandidate(
        candidate_id="c_2",
        pain_family="revenue_leak",
        description="Leaking leads",
        target_market="Agency",
        discovered_at=datetime.now(timezone.utc).isoformat(),
        independence_key="source_y"
    )
    
    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    
    # Multiple demo_booked events to trigger sqrt corroboration
    candidate.append_event(Event("e_1", "demo_booked", ts))
    score1 = EvidenceScoring.score_candidate(candidate, now)
    
    candidate.append_event(Event("e_2", "demo_booked", ts))
    score2 = EvidenceScoring.score_candidate(candidate, now)
    
    # score2 should be greater than score1 but less than 2*score1 due to sqrt corroboration
    assert score2 > score1
    assert score2 < (2 * EvidenceScoring.EVENT_WEIGHTS["demo_booked"])
    
    # Add a huge positive signal
    candidate.append_event(Event("e_3", "closed_won", ts))
    candidate.append_event(Event("e_4", "closed_won", ts))
    score3 = EvidenceScoring.score_candidate(candidate, now)
    
    # Score should be capped at SCORE_CAP
    assert score3 <= EvidenceScoring.SCORE_CAP
    
def test_retention_and_decay():
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=35)).isoformat()
    recent_ts = (now - timedelta(days=15)).isoformat()
    
    candidate = PainCandidate(
        candidate_id="c_3",
        pain_family="market_access",
        description="No access",
        target_market="Enterprise",
        discovered_at=old_ts,
        independence_key="source_z"
    )
    
    # Event older than 30 days should be ignored
    candidate.append_event(Event("e_1", "signal_detected", old_ts))
    assert EvidenceScoring.score_candidate(candidate, now) == 0.0
    
    # Event 15 days old should be decayed by half
    candidate.append_event(Event("e_2", "signal_detected", recent_ts))
    score = EvidenceScoring.score_candidate(candidate, now)
    
    expected_full_score = EvidenceScoring.EVENT_WEIGHTS["signal_detected"]
    # It decays lineary over 30 days, so 15 days is 50% decay (approx)
    assert 0 < score < expected_full_score
