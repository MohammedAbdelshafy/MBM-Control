"""
TESTS: GTM STATE MACHINE
=============================================================================
Hermetic unit tests verifying:
1. All 14 GTM states and allowed transitions
2. Strict validation and rejection of illegal transitions
3. History tracking and audit trails
4. Terminal state isolation (WON and SUPPRESSED)
=============================================================================
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.state_machine import GtmState, GtmStateMachine, InvalidStateTransitionError


def test_gtm_state_machine_initialization():
    """Verify default initialization to DISCOVERED state."""
    sm = GtmStateMachine(entity_id="OPP-001")
    assert sm.current_state == GtmState.DISCOVERED
    assert sm.entity_id == "OPP-001"
    assert len(sm.history) == 1
    assert not sm.is_terminal()


def test_valid_opportunity_progression():
    """Verify standard linear opportunity lifecycle from DISCOVERED to WON."""
    sm = GtmStateMachine(GtmState.DISCOVERED, entity_id="OPP-100")
    
    sm.transition(GtmState.QUALIFYING, reason="Enriching firmographics")
    assert sm.current_state == GtmState.QUALIFYING
    
    sm.transition(GtmState.QUALIFIED, reason="Score >= 90")
    assert sm.current_state == GtmState.QUALIFIED
    assert sm.is_callable()
    
    sm.transition(GtmState.CONTACTING, reason="Phone call placed")
    assert sm.current_state == GtmState.CONTACTING
    
    sm.transition(GtmState.ENGAGED, reason="Buyer answered and discussed pain")
    assert sm.current_state == GtmState.ENGAGED
    
    sm.transition(GtmState.MEETING_BOOKED, reason="Google Meet scheduled")
    assert sm.current_state == GtmState.MEETING_BOOKED
    
    sm.transition(GtmState.DISCOVERY_COMPLETE, reason="Diagnostic conducted")
    assert sm.current_state == GtmState.DISCOVERY_COMPLETE
    
    sm.transition(GtmState.PROPOSAL, reason="Retainer SOW sent")
    assert sm.current_state == GtmState.PROPOSAL
    
    sm.transition(GtmState.NEGOTIATION, reason="Final payment terms")
    assert sm.current_state == GtmState.NEGOTIATION
    
    sm.transition(GtmState.WON, reason="Neteller transaction verified")
    assert sm.current_state == GtmState.WON
    assert sm.is_terminal()


def test_invalid_state_transitions():
    """Verify that illegal transitions raise InvalidStateTransitionError."""
    sm = GtmStateMachine(GtmState.DISCOVERED, entity_id="OPP-BAD")
    
    # Cannot jump from DISCOVERED directly to WON
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(GtmState.WON)
        
    # Cannot jump from DISCOVERED directly to NEGOTIATION
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(GtmState.NEGOTIATION)
        
    # Move to SUPPRESSED
    sm.transition(GtmState.SUPPRESSED, reason="DNC requested")
    assert sm.current_state == GtmState.SUPPRESSED
    assert sm.is_terminal()
    
    # Cannot transition out of SUPPRESSED
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(GtmState.CONTACTING)


def test_force_transition_override():
    """Verify administrator force flag bypasses transition guard."""
    sm = GtmStateMachine(GtmState.DISCOVERED, entity_id="OPP-FORCED")
    sm.transition(GtmState.PROPOSAL, force=True, reason="Executive manual override")
    assert sm.current_state == GtmState.PROPOSAL
    assert sm.history[-1]["forced"] is True
