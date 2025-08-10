"""
Tests for growthkit.reports.exec_config
"""

from growthkit.reports.exec_config import (
    get_report_template,
    list_available_templates,
    validate_template_data,
)


def test_list_and_get_templates_present():
    """
    Test that the list of available templates and the get_report_template function work.
    """
    names = list_available_templates()
    # Expect known templates to be present
    assert "mtd_performance" in names
    assert get_report_template("mtd_performance") is not None


def test_validate_template_data_flags_missing_and_optionals():
    """
    Test that the validate_template_data function flags missing and optional data sources.
    """
    tmpl = get_report_template("mtd_performance")
    assert tmpl is not None

    # Provide only a subset of data sources
    available = ["shopify_new_returning"]
    result = validate_template_data(tmpl, available)

    # Executive Summary requires shopify_new_returning → valid True
    exec_section = result["Executive Summary"]
    assert exec_section["valid"] is True
    # Optional GA4 becomes available only when provided
    assert exec_section["available_optional"] == []

    # Customer Mix also requires shopify_new_returning → valid True
    cust_section = result["Customer Mix"]
    assert cust_section["valid"] is True
    assert cust_section["missing_required"] == []

    # Channel Performance requires ga4_channel_group → should be missing
    chan_section = result["Channel Performance"]
    assert chan_section["valid"] is False
    assert chan_section["missing_required"] == ["ga4_channel_group"]

    # Now include the optional/required GA4 and re-validate
    available2 = ["shopify_new_returning", "ga4_channel_group", "shopify_products"]
    result2 = validate_template_data(tmpl, available2)
    exec_section2 = result2["Executive Summary"]
    cust_section2 = result2["Customer Mix"]
    chan_section2 = result2["Channel Performance"]

    assert exec_section2["valid"] is True
    assert exec_section2["available_optional"] == ["ga4_channel_group"]
    assert cust_section2["valid"] is True
    assert chan_section2["valid"] is True
    assert chan_section2["missing_required"] == []
