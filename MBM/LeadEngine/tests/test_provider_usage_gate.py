"""Provider credit-budget approval contracts."""

import pytest

from MBM.LeadEngine.connectors.usage_gate import (
    ProviderBudgetDenied,
    authorize_provider_usage,
)


def test_zero_credit_company_or_people_search_does_not_require_credit_approval():
    result = authorize_provider_usage(
        provider="APOLLO",
        operation="PEOPLE_SEARCH",
        estimated_credits=0,
        credits_available=80,
    )
    assert result.authorized is True
    assert result.estimated_credits == 0
    assert result.approval_reference is None


def test_credit_consuming_enrichment_is_blocked_without_explicit_approval():
    with pytest.raises(ProviderBudgetDenied, match="explicit approval"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="PEOPLE_ENRICHMENT",
            estimated_credits=9,
            credits_available=80,
        )


def test_approved_enrichment_must_fit_approved_budget_and_available_credits():
    result = authorize_provider_usage(
        provider="APOLLO",
        operation="PEOPLE_ENRICHMENT",
        estimated_credits=9,
        credits_available=80,
        approved=True,
        approval_reference="FOUNDER-APPROVAL-2026-10-30-01",
        approved_max_credits=10,
    )
    assert result.authorized is True
    assert result.estimated_credits == 9
    assert result.approval_reference == "FOUNDER-APPROVAL-2026-10-30-01"


def test_estimate_above_approved_cap_is_denied():
    with pytest.raises(ProviderBudgetDenied, match="approved cap"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="PHONE_WATERFALL",
            estimated_credits=25,
            credits_available=160,
            approved=True,
            approval_reference="APPROVAL-1",
            approved_max_credits=20,
        )


def test_estimate_above_remaining_provider_credits_is_denied():
    with pytest.raises(ProviderBudgetDenied, match="available credits"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="PHONE_WATERFALL",
            estimated_credits=25,
            credits_available=20,
            approved=True,
            approval_reference="APPROVAL-1",
            approved_max_credits=30,
        )


def test_unknown_cost_requires_approved_bounded_ceiling():
    with pytest.raises(ProviderBudgetDenied, match="known upper bound"):
        authorize_provider_usage(
            provider="CLAY",
            operation="MULTI_PROVIDER_WATERFALL",
            estimated_credits=None,
            credits_available=100,
            approved=True,
            approval_reference="APPROVAL-2",
            approved_max_credits=None,
        )

    result = authorize_provider_usage(
        provider="CLAY",
        operation="MULTI_PROVIDER_WATERFALL",
        estimated_credits=None,
        credits_available=100,
        approved=True,
        approval_reference="APPROVAL-3",
        approved_max_credits=30,
    )
    assert result.authorized is True
    assert result.estimated_credits is None
    assert result.approved_max_credits == 30


@pytest.mark.parametrize("credits", [-1, float("inf"), float("nan")])
def test_invalid_credit_estimates_are_rejected(credits):
    with pytest.raises(ValueError, match="credits"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="PEOPLE_SEARCH",
            estimated_credits=credits,
            credits_available=100,
        )


def test_zero_cost_does_not_override_approval_for_contact_data_access():
    with pytest.raises(ProviderBudgetDenied, match="contact-data approval"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="PEOPLE_SEARCH_WITH_CONTACT_DETAILS",
            estimated_credits=0,
            credits_available=80,
            personal_contact_access=True,
        )

    result = authorize_provider_usage(
        provider="APOLLO",
        operation="PEOPLE_SEARCH_WITH_CONTACT_DETAILS",
        estimated_credits=0,
        credits_available=80,
        personal_contact_access=True,
        contact_data_approved=True,
        approval_reference="FOUNDER-CONTACT-APPROVAL-01",
    )
    assert result.authorized is True


def test_agent_quality_assessment_requires_all_mandatory_checks():
    from MBM.LeadEngine.connectors.agent_quality import assess_agent_operation

    result = assess_agent_operation({
        "capability_match": True,
        "evidence_provenance": True,
        "identity_confidence": True,
        "duplicate_check": True,
        "suppression_check": True,
        "privacy_scope_check": True,
        "contact_scope_check": False,
    }, require_contact_scope=True)

    assert result.passed is False
    assert result.score < 1.0
    assert "contact_scope_check" in result.failed_checks


def test_agent_quality_can_authorize_paid_work_within_daily_cap_without_human_approval():
    quality_checks = {
        "capability_match": True,
        "evidence_provenance": True,
        "identity_confidence": True,
        "duplicate_check": True,
        "suppression_check": True,
        "privacy_scope_check": True,
    }
    result = authorize_provider_usage(
        provider="APOLLO",
        operation="COMPANY_ENRICHMENT",
        estimated_credits=2,
        credits_available=8,
        quality_checks=quality_checks,
        agent_policy_id="mbm-customer-acquisition-v1",
        daily_budget_limit=5,
        credits_spent_today=1,
    )

    assert result.authorized is True
    assert result.credits_ceiling == 2
    assert result.agent_policy_id == "mbm-customer-acquisition-v1"
    assert result.quality_passed is True


def test_agent_quality_budget_blocks_spend_above_daily_limit():
    quality_checks = {
        "capability_match": True,
        "evidence_provenance": True,
        "identity_confidence": True,
        "duplicate_check": True,
        "suppression_check": True,
        "privacy_scope_check": True,
    }
    with pytest.raises(ProviderBudgetDenied, match="daily agent budget"):
        authorize_provider_usage(
            provider="APOLLO",
            operation="COMPANY_ENRICHMENT",
            estimated_credits=5,
            credits_available=20,
            quality_checks=quality_checks,
            agent_policy_id="mbm-customer-acquisition-v1",
            daily_budget_limit=5,
            credits_spent_today=1,
        )
