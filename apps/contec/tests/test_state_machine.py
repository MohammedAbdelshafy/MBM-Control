"""State machine: legal transitions, opt-out terminality, retry/cooldown."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_history  # noqa: F401  (pytest rootdir insertion)
from contec.real_estate_media.state_machine import (
    DEFAULT_POLICY, IllegalTransition, OptedOut,
    can_transition, guard_contact, retry_allowed, transition,
)

DO_NOT_CONTACT = "DO_NOT_CONTACT"


class TestTransitions:
    def test_happy_path_to_won(self):
        path = ["READY", "DIALED", "CONNECTED", "INTERESTED",
                "SAMPLE_REQUESTED", "SAMPLE_SENT", "QUOTED", "NEGOTIATING", "WON"]
        cur = path[0]
        for nxt in path[1:]:
            res = transition(cur, nxt)
            cur = res["to"]
        assert cur == "WON"

    def test_illegal_jump_rejected(self):
        with pytest.raises(IllegalTransition):
            transition("READY", "QUOTED")

    def test_opt_out_legal_from_anywhere_and_terminal(self):
        for state in ["READY", "CONNECTED", "SAMPLE_SENT", "NEGOTIATING", "WON"]:
            if state in ("WON", "LOST"):
                continue
            assert can_transition(state, DO_NOT_CONTACT)
        assert can_transition(DO_NOT_CONTACT, "READY") is False

    def test_contact_guard_raises_on_optout(self):
        with pytest.raises(OptedOut):
            guard_contact("DO_NOT_CONTACT")


class TestRetryAndCooldown:
    def _pol(self, **kw):
        return {**DEFAULT_POLICY, **kw}

    def test_under_retry_limit_allowed(self):
        hist = make_history("NO_ANSWER")
        ok, why = retry_allowed(hist, self._pol(max_no_answer_retries=3))
        assert ok

    def test_retry_limit_blocks(self):
        hist = make_history("NO_ANSWER", "NO_ANSWER", "NO_ANSWER")
        ok, why = retry_allowed(hist, self._pol(max_no_answer_retries=3))
        assert not ok and why == "retry_limit_reached"

    def test_cooldown_blocks_recent_attempt(self, now):
        hist = make_history("NO_ANSWER", start=now - timedelta(hours=1))
        ok, why = retry_allowed(hist, self._pol(no_answer_cooldown_hours=48), now=now)
        assert not ok and why == "cooldown_active"

    def test_cooldown_expires(self, now):
        hist = make_history("NO_ANSWER", start=now - timedelta(hours=50))
        ok, _ = retry_allowed(hist, self._pol(no_answer_cooldown_hours=48), now=now)
        assert ok

    def test_callback_gap_enforced(self, now):
        hist = make_history("CALLBACK", start=now - timedelta(hours=1), gap_hours=0)
        ok, why = retry_allowed(hist, {}, now=now)
        assert not ok and why == "callback_gap"
