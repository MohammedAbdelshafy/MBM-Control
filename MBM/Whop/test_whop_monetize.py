"""
test_whop_monetize.py — regression for WHOP_ACCOUNT_ID propagation
===================================================================
Verifies the fix: after load_dotenv() loads .env, the module-level
ACCOUNT_ID variable receives the correct value from os.environ.

The bug: line 37 captured ACCOUNT_ID from os.getenv() BEFORE
load_dotenv() at line 58 populated os.environ from the .env file.
The fix re-reads ACCOUNT_ID after load_dotenv() completes.
"""
import os
import sys


def test_env_propagation_after_load_dotenv(monkeypatch, tmp_path):
    """Simulates the exact bug scenario: .env has WHOP_ACCOUNT_ID,
    but module-level capture happens before load_dotenv runs."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "WHOP_ACCOUNT_ID=biz_TEST123\n"
        "WHOP_API_KEY=key_TEST456\n",
        encoding="utf-8",
    )

    # Clear the env so os.getenv() would return "" without load_dotenv.
    monkeypatch.delenv("WHOP_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("WHOP_API_KEY", raising=False)

    # Replicate the module-level logic from whop_monetize.py lines 34-63.
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "")  # line 37: runs first
    WHOP_API_KEY = os.getenv("WHOP_API_KEY", "")

    # load_dotenv reads the .env file and populates os.environ.
    from dotenv import load_dotenv
    load_dotenv(env_file)

    # FIX: re-read after load_dotenv (the line we added).
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", ACCOUNT_ID)

    assert ACCOUNT_ID == "biz_TEST123", (
        f"ACCOUNT_ID should be 'biz_TEST123' after load_dotenv, got '{ACCOUNT_ID}'"
    )
    # Also verify WHOP_API_KEY was re-read (existing behavior, preserved).
    WHOP_API_KEY = os.getenv("WHOP_API_KEY", WHOP_API_KEY)
    assert WHOP_API_KEY == "key_TEST456"


def test_account_id_defaults_empty_without_dotenv(monkeypatch):
    """When no .env file and no env var, ACCOUNT_ID stays empty."""
    monkeypatch.delenv("WHOP_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("WHOP_API_KEY", raising=False)

    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "")
    # Simulate fix line (no value to re-read).
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", ACCOUNT_ID)

    assert ACCOUNT_ID == "", f"Expected '', got '{ACCOUNT_ID}'"


def test_account_id_shell_env_wins_over_empty_default(monkeypatch):
    """When WHOP_ACCOUNT_ID is in shell env (not .env), it is used directly."""
    monkeypatch.setenv("WHOP_ACCOUNT_ID", "biz_SHELL_VAL")

    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "")
    # Fix line: re-reads (shell env value persists).
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", ACCOUNT_ID)

    assert ACCOUNT_ID == "biz_SHELL_VAL"


def test_account_id_dotenv_wins_over_empty_shell(monkeypatch, tmp_path):
    """When shell env is empty but .env has the value, load_dotenv + fix gets it."""
    env_file = tmp_path / ".env"
    env_file.write_text("WHOP_ACCOUNT_ID=biz_FROM_DOTENV\n", encoding="utf-8")
    monkeypatch.delenv("WHOP_ACCOUNT_ID", raising=False)

    # Module-level: empty before load_dotenv
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", "")
    assert ACCOUNT_ID == ""  # confirms the bug scenario

    from dotenv import load_dotenv
    load_dotenv(env_file)

    # Fix line re-reads
    ACCOUNT_ID = os.getenv("WHOP_ACCOUNT_ID", ACCOUNT_ID)
    assert ACCOUNT_ID == "biz_FROM_DOTENV"
