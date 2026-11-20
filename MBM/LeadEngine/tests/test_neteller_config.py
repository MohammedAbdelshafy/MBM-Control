"""Tests for environment-backed Neteller payment-link construction."""

import importlib
from urllib.parse import parse_qs, urlparse

import pytest

import MBM.Scripts.neteller_config as neteller_config


def _reload_config():
    return importlib.reload(neteller_config)


def test_checkout_link_requires_explicit_wallet_configuration(monkeypatch):
    monkeypatch.delenv("NETELLER_EMAIL", raising=False)
    monkeypatch.delenv("NETELLER_ACCOUNT_ID", raising=False)

    config = _reload_config()

    with pytest.raises(RuntimeError, match="NETELLER_EMAIL and NETELLER_ACCOUNT_ID"):
        config.neteller_link(amount=50, item="AI_FRONT_DESK_PILOT")


def test_checkout_link_uses_only_environment_supplied_wallet_details(monkeypatch):
    monkeypatch.setenv("NETELLER_EMAIL", "payments@example.test")
    monkeypatch.setenv("NETELLER_ACCOUNT_ID", "test-account-001")
    monkeypatch.setenv("NETELLER_PAY_BASE", "https://payments.example.test/member-pay")

    config = _reload_config()
    link = config.neteller_link(amount=125.5, item="MIA-PILOT", currency="usd")

    parsed = urlparse(link)
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "payments.example.test"
    assert params["email"] == ["payments@example.test"]
    assert params["account"] == ["test-account-001"]
    assert params["amount"] == ["125.50"]
    assert params["currency"] == ["USD"]
    assert params["item"] == ["MIA-PILOT"]


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_checkout_link_rejects_invalid_amounts(monkeypatch, amount):
    monkeypatch.setenv("NETELLER_EMAIL", "payments@example.test")
    monkeypatch.setenv("NETELLER_ACCOUNT_ID", "test-account-001")
    config = _reload_config()

    with pytest.raises(ValueError, match="amount"):
        config.neteller_link(amount=amount, item="VALID-SKU")


def test_checkout_link_rejects_empty_item(monkeypatch):
    monkeypatch.setenv("NETELLER_EMAIL", "payments@example.test")
    monkeypatch.setenv("NETELLER_ACCOUNT_ID", "test-account-001")
    config = _reload_config()

    with pytest.raises(ValueError, match="item"):
        config.neteller_link(amount=50, item="  ")
