#!/usr/bin/env python3
"""
Report Configuration Templates

This module defines different report templates and their data requirements.
You can easily add new report types or modify existing ones here.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class ReportSection:
    """Defines a section of a report"""
    name: str
    required_data: List[str]  # Data sources needed
    optional_data: List[str] = None
    template: str = ""

@dataclass
class ReportTemplate:
    """Defines a complete report template"""
    name: str
    description: str
    sections: List[ReportSection]

# Define available report templates
REPORT_TEMPLATES = {
    'mtd_performance': ReportTemplate(
        name="MTD Performance Summary",
        description="Month-to-date performance analysis with customer mix and channel breakdown",
        sections=[
            ReportSection(
                name="Executive Summary",
                required_data=['shopify_new_returning'],
                optional_data=['ga4_channel_group'],
                template="""## EXECUTIVE SUMMARY

- **Total Business Revenue:** ${total_revenue:,.0f}
- **New Customer Contribution:** {new_pct:.1f}%
- **Returning Customer Contribution:** {returning_pct:.1f}%
- **Total Orders:** {total_orders:,}
{ga4_summary}

**Summary Insight:**
> {insight_text}
"""
            ),
            ReportSection(
                name="Customer Mix",
                required_data=['shopify_new_returning'],
                template="""## Customer Mix (New vs. Returning)

| Segment               | Revenue | Orders | AOV | % of Total Revenue |
|-----------------------|---------|--------|-----|-------------------|
| New-to-Brand Users    | ${new_revenue:,.0f} | {new_orders:,} | ${new_aov:.0f} | {new_pct:.1f}% |
| Returning Customers   | ${returning_revenue:,.0f} | {returning_orders:,} | ${returning_aov:.0f} | {returning_pct:.1f}% |
| **Total**             | ${total_revenue:,.0f} | {total_orders:,} | ${total_aov:.0f} | **100%** |

**Insight:**
> New customers generated {new_pct:.1f}% of total revenue with an AOV ${aov_diff:+.0f} {'higher' if aov_diff > 0 else 'lower'} than returning buyers.
"""
            ),
            ReportSection(
                name="Channel Performance",
                required_data=['ga4_channel_group'],
                template="""## Channel Performance (GA4)

| Channel | Sessions | Revenue | Revenue per Session |
|---------|----------|---------|-------------------|
{channel_rows}
"""
            ),
            ReportSection(
                name="Product Performance",
                required_data=['shopify_products'],
                template="""## Top Products Performance

| Product Name | Revenue | Items Sold |
|--------------|---------|------------|
{product_rows}
"""
            )
        ]
    ),

    'weekly_growth': ReportTemplate(
        name="Weekly Growth Report",
        description="Week-over-week growth analysis with channel performance",
        sections=[
            ReportSection(
                name="Executive Summary",
                required_data=['shopify_total_sales', 'ga4_channel_group'],
                template="""## Executive Summary

**Period Performance:**
- Total Revenue: ${total_revenue:,.0f} ({revenue_change:+.1f}% WoW)
- Total Sessions: {total_sessions:,} ({session_change:+.1f}% WoW)
- Conversion Rate: {conversion_rate:.2f}% ({cvr_change:+.2f}pp WoW)

**Key Highlights:**
{highlights}
"""
            ),
            ReportSection(
                name="Channel Breakdown",
                required_data=['ga4_channel_group'],
                optional_data=['northbeam_spend'],
                template="""## Channel Performance

| Channel | Sessions | Revenue | ROAS | Change WoW |
|---------|----------|---------|------|------------|
{channel_performance_rows}
"""
            )
        ]
    ),

    'affiliate_analysis': ReportTemplate(
        name="Affiliate Performance Analysis",
        description="Detailed breakdown of all affiliate sources and performance",
        sections=[
            ReportSection(
                name="Affiliate Overview",
                required_data=['ga4_source_medium'],
                optional_data=['northbeam_spend'],
                template="""## Affiliate Performance Overview

**Total Affiliate Revenue:** ${total_affiliate_revenue:,.0f}
**Total Affiliate Sessions:** {total_affiliate_sessions:,}

### Paid Affiliates
{paid_affiliate_table}

### Organic Referrals
{organic_referral_table}
"""
            )
        ]
    )
}

# Data source configurations
DATA_SOURCE_CONFIG = {
    'ga4_source_medium': {
        'pattern': '*source_medium*.csv',
        'description': 'GA4 Session source/medium data',
        'date_column': 'Date',
        'date_format': '%Y%m%d',
        'skip_rows': 9,
        'required_columns': ['Session source / medium', 'Sessions', 'Total revenue']
    },
    'ga4_channel_group': {
        'pattern': '*default_channel_group*.csv',
        'description': 'GA4 Default channel group data',
        'date_column': 'Date',
        'date_format': '%Y%m%d',
        'skip_rows': 9,
        'required_columns': ['Default channel group', 'Sessions', 'Total revenue']
    },
    'shopify_total_sales': {
        'pattern': '*Total sales over time*.csv',
        'description': 'Shopify total sales over time',
        'date_column': None,  # Usually monthly data
        'required_columns': ['Total sales']
    },
    'shopify_new_returning': {
        'pattern': '*New vs returning*.csv',
        'description': 'Shopify new vs returning customer sales',
        'date_column': 'Month',
        'required_columns': ['New or returning customer', 'Total sales', 'Orders']
    },
    'shopify_products': {
        'pattern': '*Total sales by product*.csv',
        'description': 'Shopify product sales breakdown',
        'date_column': 'Day',
        'skip_rows': 0,
        'required_columns': ['Product title', 'Total sales', 'Net items sold']
    },
    'northbeam_spend': {
        'pattern': '*northbeam*.csv',
        'description': 'Northbeam spend and attribution data',
        'date_column': 'Date',
        'required_columns': ['Spend', 'Revenue']
    }
}

def get_report_template(template_name: str) -> Optional[ReportTemplate]:
    """Get a report template by name"""
    return REPORT_TEMPLATES.get(template_name)

def list_available_templates() -> List[str]:
    """List all available report template names"""
    return list(REPORT_TEMPLATES.keys())

def get_data_source_config(source_name: str) -> Optional[Dict]:
    """Get configuration for a data source"""
    return DATA_SOURCE_CONFIG.get(source_name)

def validate_template_data(template: ReportTemplate, available_data: List[str]) -> Dict[str, bool]:
    """Check if required data is available for a template"""
    validation = {}

    for section in template.sections:
        section_valid = True
        missing_required = []

        for required in section.required_data:
            if required not in available_data:
                section_valid = False
                missing_required.append(required)

        validation[section.name] = {
            'valid': section_valid,
            'missing_required': missing_required,
            'available_optional': [opt for opt in (section.optional_data or []) if opt in available_data]
        }

    return validation 