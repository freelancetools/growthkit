#!/usr/bin/env python3
"""
Weekly Product & Category Growth Report

This script extends the channel-level weekly report by mapping each campaign/ad
row to a specific product (and its category) based on the naming found in the
Ad Name → Ad Set Name → Campaign Name cascade.  It then outputs additional
markdown tables summarising performance by product and by product category.

The original channel-level analytics remain intact via re-use of
`report_analysis_weekly` helper functions.
"""
import re
import os
import glob
import argparse
from pathlib import Path
from typing import Iterable, Sequence
from datetime import datetime, timedelta, date

import numpy as np
import pandas as pd

from growthkit.reports import product_data
from growthkit.reports.file_selector import select_csv_file

# ---------------------------------------------------------------------------
# 🔍  Repository-aware path helpers
# ---------------------------------------------------------------------------


def _looks_like_repo_root(path: Path, markers: Sequence[str]) -> bool:
    """Return ``True`` if *path* contains any of the *marker* files/dirs."""
    for marker in markers:
        if (path / marker).exists():
            return True
    return False


def project_root(markers: Sequence[str] | None = None) -> Path:
    """Return the absolute ``Path`` of the repo root.

    The function walks *up* from *this* file until it discovers a directory
    that contains at least one *marker* (default: ``pyproject.toml`` or
    ``.git``).  If none is found we fall back to two parents above this file
    so that execution continues gracefully even in unusual layouts (e.g. when
    the code lives inside a zipfile or temp directory).
    """
    if markers is None:
        markers = ("pyproject.toml", ".git")

    cur = Path(__file__).resolve()
    for parent in [cur] + list(cur.parents):
        if _looks_like_repo_root(parent, markers):
            return parent
    # Fallback: assume utils/paths.py is at ``src/growthkit/utils/`` so two
    # parents up should be the project root.
    return cur.parents[2]


def find_latest_in_repo(pattern: str, markers: Sequence[str] | None = None) -> str | None:
    """Return the *newest* file matching *pattern* anywhere inside the repo.

    Parameters
    ----------
    pattern : str
        Unix-shell wildcard pattern (e.g. ``"google-2024*-daily*.csv"``).
    markers : Sequence[str] | None, optional
        Override the *project_root* marker list if required.

    Notes
    -----
    • The search is *recursive* (`Path.rglob`) so performance is O(number of
      files). If your repo is *very* large you may want to narrow the search
      by first identifying likely top-level directories.
    • Returns ``None`` when no match is found so callers must handle that case.
    """
    root = project_root(markers)
    matches: Iterable[Path] = root.rglob(pattern)
    latest: Path | None = None
    latest_mtime = -1.0
    for p in matches:
        try:
            mtime = p.stat().st_mtime
        except (FileNotFoundError, PermissionError):
            continue  # Skip paths we cannot stat
        if mtime > latest_mtime:
            latest = p
            latest_mtime = mtime
    return str(latest) if latest else None


__all__ = [
    "project_root",
    "find_latest_in_repo",
]


# -------------------------------------------------------------
# Channel-level functions
# -------------------------------------------------------------

def load_and_clean_data():
    """Load and clean the 7-day sales data"""
    csv_file = select_csv_file(
        directory="data/ads",
        file_pattern="*sales_data-eskiin*csv",
        prompt_message="\nSelect Northbeam sales CSV (or 'q' to quit): ",
        max_items=10,
    )
    if not csv_file:
        print("No file selected. Exiting.")
        return None

    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Successfully loaded data with {len(df)} rows")

        numeric_cols = [
            'spend', 'cac', 'cac_1st_time', 'roas', 'roas_1st_time',
            'aov', 'aov_1st_time', 'ecr', 'ecr_1st_time', 'ecpnv',
            'platformreported_cac', 'platformreported_roas',
            'new_customer_percentage', 'attributed_rev', 'attributed_rev_1st_time',
            'transactions', 'transactions_1st_time', 'visits',
            'web_revenue', 'web_transactions',
            'meta_shops_revenue', 'meta_shops_transactions',
            'tiktok_shops_revenue', 'tiktok_shops_transactions',
            'rev'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.fillna(0)

        def promote(src_rev, src_txn, label):
            mask = (df['attributed_rev'] == 0) & (df[src_rev] > 0)
            if mask.any():
                df.loc[mask, 'attributed_rev'] = df.loc[mask, src_rev]
                if 'attributed_rev_1st_time' in df.columns:
                    df.loc[mask, 'attributed_rev_1st_time'] = df.loc[mask, src_rev]
                if 'transactions' in df.columns and src_txn in df.columns:
                    df.loc[mask, 'transactions'] = df.loc[mask, src_txn]
                if 'transactions_1st_time' in df.columns and src_txn in df.columns:
                    df.loc[mask, 'transactions_1st_time'] = df.loc[mask, src_txn]
                df.loc[mask, f'used_{label}_metrics'] = True
                print(f"ℹ️  Applied {label} fallback for {mask.sum()} rows")

        if {'web_revenue', 'web_transactions'}.issubset(df.columns):
            promote('web_revenue', 'web_transactions', 'web')
        if {'meta_shops_revenue', 'meta_shops_transactions'}.issubset(df.columns):
            promote('meta_shops_revenue', 'meta_shops_transactions', 'meta_shops')
        if {'tiktok_shops_revenue', 'tiktok_shops_transactions'}.issubset(df.columns):
            promote('tiktok_shops_revenue', 'tiktok_shops_transactions', 'tiktok_shops')

        if 'rev' in df.columns:
            mask_rev = (df['attributed_rev'] == 0) & (df['rev'] > 0)
            if mask_rev.any():
                df.loc[mask_rev, 'attributed_rev'] = df.loc[mask_rev, 'rev']
                df.loc[mask_rev, 'used_rev_metrics'] = True
                print(f"ℹ️  Promoted 'rev' cash snapshot for {mask_rev.sum()} rows")

        required_platform_col = 'breakdown_platform_northbeam'
        if required_platform_col not in df.columns:
            alternative_cols = ['platform', 'channel', 'breakdown_platform']
            found = False
            for alt in alternative_cols:
                if alt in df.columns:
                    df[required_platform_col] = df[alt]
                    print(
                        f"ℹ️  Mapped column '{alt}' -> '{required_platform_col}' for compatibility"
                    )
                    found = True
                    break
            if not found:
                print("⚠️  No platform column found. Inserting placeholder 'Unknown'.")
                df[required_platform_col] = 'Unknown'

        return df
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        print(f"❌ Error loading CSV data: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"❌ Error processing data: {e}")
        return None


def analyze_channel_performance(df):
    """Analyze performance by marketing channel"""
    print("\n" + "="*60)
    print("📊 CHANNEL PERFORMANCE ANALYSIS")
    print("="*60)
    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()
    if len(accrual_df) == 0:
        print("⚠️ No Accrual Performance data found")
        return {}
    channel_summary = accrual_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'attributed_rev': 'sum',
        'attributed_rev_1st_time': 'sum',
        'transactions': 'sum',
        'transactions_1st_time': 'sum',
        'visits': 'sum',
        'new_visits': 'sum'
    }).round(2)
    channel_summary['roas'] = (
        channel_summary['attributed_rev'] / channel_summary['spend']
    ).replace([np.inf], 0).round(2)
    channel_summary['roas_1st_time'] = (
        channel_summary['attributed_rev_1st_time'] / channel_summary['spend']
    ).replace([np.inf], 0).round(2)
    channel_summary['cac'] = (
        channel_summary['spend'] / channel_summary['transactions']
    ).replace([np.inf], 0).round(2)
    channel_summary['cac_1st_time'] = (
        channel_summary['spend'] / channel_summary['transactions_1st_time']
    ).replace([np.inf], 0).round(2)
    channel_summary['aov'] = (
        channel_summary['attributed_rev'] / channel_summary['transactions']
    ).replace([np.inf], 0).round(2)
    channel_summary['ecr'] = (
        channel_summary['transactions'] / channel_summary['visits']
    ).replace([np.inf], 0).round(4)
    channel_summary['percent_new_visits'] = (
        channel_summary['new_visits'] / channel_summary['visits'] * 100
    ).replace([np.inf], 0).round(1)
    channel_summary = channel_summary.sort_values('spend', ascending=False)
    print("\nTOP PERFORMING CHANNELS BY SPEND:")
    print("-" * 60)
    for platform, row in channel_summary.head(10).iterrows():
        if row['spend'] > 0:
            print(
                f"{platform:<20} | Spend: ${row['spend']:>10,.2f} | "
                f"ROAS: {row['roas']:>5.2f} | CAC: ${row['cac']:>7.2f} | "
                f"AOV: ${row['aov']:>6.2f}"
            )
    return channel_summary

def analyze_campaign_performance(df):
    """Analyze individual campaign performance (migrated)."""
    print("\n" + "="*60)
    print("🚀 TOP CAMPAIGN PERFORMANCE")
    print("="*60)

    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()
    significant_campaigns = accrual_df[accrual_df['spend'] > 100].copy()
    revenue_only = accrual_df[(accrual_df['spend'] == 0) & (accrual_df['attributed_rev'] > 0)].copy()

    if not revenue_only.empty:
        revenue_only['aov'] = revenue_only.apply(
            lambda r: (r['attributed_rev'] / r['transactions']) if r['transactions'] else 0, axis=1
        )

    if len(significant_campaigns) == 0:
        print("⚠️ No campaigns with significant spend found")
        return {}

    significant_campaigns['roas'] = (
        significant_campaigns['attributed_rev'] / significant_campaigns['spend']
    ).replace([np.inf], 0)
    significant_campaigns['cac'] = (
        significant_campaigns['spend'] / significant_campaigns['transactions']
    ).replace([np.inf], 0)
    if 'transactions_1st_time' in significant_campaigns.columns:
        significant_campaigns['cac_1st_time'] = (
            significant_campaigns['spend'] / significant_campaigns['transactions_1st_time']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['cac_1st_time'] = 0
    significant_campaigns['aov'] = (
        significant_campaigns['attributed_rev'] / significant_campaigns['transactions']
    ).replace([np.inf], 0)
    if 'attributed_rev_1st_time' in significant_campaigns.columns and 'transactions_1st_time' in significant_campaigns.columns:
        significant_campaigns['aov_1st_time'] = (
            significant_campaigns['attributed_rev_1st_time'] / significant_campaigns['transactions_1st_time']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['aov_1st_time'] = 0
    if 'attributed_rev_1st_time' in significant_campaigns.columns:
        significant_campaigns['roas_1st_time'] = (
            significant_campaigns['attributed_rev_1st_time'] / significant_campaigns['spend']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['roas_1st_time'] = 0

    print("\nTOP 10 CAMPAIGNS BY ROAS:")
    print("-" * 100)
    for _, row in significant_campaigns.nlargest(10, 'roas').iterrows():
        if row['roas'] > 0:
            print(
                f"{row['breakdown_platform_northbeam']:<12} | {row['campaign_name'][:40]:<40} | "
                f"ROAS: {row['roas']:>5.2f} | Spend: ${row['spend']:>8,.2f}"
            )

    print("\nTOP 10 CAMPAIGNS BY SPEND:")
    print("-" * 100)
    for _, row in significant_campaigns.nlargest(10, 'spend').iterrows():
        print(
            f"{row['breakdown_platform_northbeam']:<12} | {row['campaign_name'][:40]:<40} | "
            f"Spend: ${row['spend']:>8,.2f} | ROAS: {row['roas']:>5.2f}"
        )

    return significant_campaigns, revenue_only

def analyze_first_time_metrics(df):
    """Analyze first-time customer metrics by channel (Accrual only)."""
    print("\n" + "=" * 60)
    print("👥 FIRST-TIME CUSTOMER METRICS BY CHANNEL")
    print("=" * 60)

    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()
    if len(accrual_df) == 0:
        print("⚠️ No Accrual Performance data found")
        return {}

    grouped = accrual_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'attributed_rev_1st_time': 'sum',
        'transactions_1st_time': 'sum'
    })

    grouped['cac_1st_time'] = (grouped['spend'] / grouped['transactions_1st_time']).replace([np.inf], 0)
    grouped['roas_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['spend']).replace([np.inf], 0)
    grouped['aov_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['transactions_1st_time']).replace([np.inf], 0)

    first_time_metrics = grouped.round(2).sort_values('spend', ascending=False)

    print("\nTOP CHANNELS ‑ FIRST-TIME CUSTOMER METRICS:")
    print("-" * 100)
    for platform, row in first_time_metrics.head(10).iterrows():
        if row['spend'] > 100:
            print(
                f"{platform:<15} | CAC 1st: ${row['cac_1st_time']:>7.2f} | "
                f"ROAS 1st: {row['roas_1st_time']:>5.2f} | "
                f"AOV 1st: ${row['aov_1st_time']:>7.2f} | "
                f"Spend: ${row['spend']:>8.2f}"
            )

    return first_time_metrics

def generate_executive_summary(channel_summary):
    """Generate executive summary metrics (migrated)."""
    print("\n" + "="*60)
    print("📈 EXECUTIVE SUMMARY METRICS")
    print("="*60)

    total_spend = channel_summary['spend'].sum()
    total_revenue = channel_summary['attributed_rev'].sum()
    total_revenue_1st_time = channel_summary['attributed_rev_1st_time'].sum()
    total_transactions = channel_summary['transactions'].sum()
    total_visits = channel_summary['visits'].sum()

    overall_roas = total_revenue / total_spend if total_spend > 0 else 0
    overall_roas_1st_time = total_revenue_1st_time / total_spend if total_spend > 0 else 0
    overall_cac = total_spend / total_transactions if total_transactions > 0 else 0
    overall_aov = total_revenue / total_transactions if total_transactions > 0 else 0
    overall_ecr = total_transactions / total_visits if total_visits > 0 else 0

    print(f"💰 Total Spend: ${total_spend:,.2f}")
    print(f"💵 Total Revenue: ${total_revenue:,.2f}")
    print(f"🎯 Overall ROAS: {overall_roas:.2f} (First-Time: {overall_roas_1st_time:.2f})")
    print(f"💸 Overall CAC: ${overall_cac:.2f}")
    print(f"🛒 Overall AOV: ${overall_aov:.2f}")
    print(f"📊 Overall ECR: {overall_ecr:.4f} ({overall_ecr*100:.2f}%)")
    print(f"🔄 Total Transactions: {int(total_transactions)}")
    print(f"👥 Total Visits: {int(total_visits)}")

    top_3_channels = channel_summary.head(3)
    print("\n🏆 TOP 3 CHANNELS BY SPEND:")
    for i, (platform, row) in enumerate(top_3_channels.iterrows(), 1):
        if row['spend'] > 0:
            print(f"   {i}. {platform}: ${row['spend']:,.2f} (ROAS: {row['roas']:.2f})")

    return {
        'total_spend': total_spend,
        'total_revenue': total_revenue,
        'overall_roas': overall_roas,
        'overall_cac': overall_cac,
        'overall_aov': overall_aov,
        'overall_roas_1st_time': overall_roas_1st_time,
        'overall_ecr': overall_ecr,
        'total_transactions': total_transactions,
        'total_visits': total_visits
    }

def analyze_attribution_modes(df):
    """Compare Cash vs Accrual accounting modes (migrated)."""
    print("\n" + "="*60)
    print("🔍 ATTRIBUTION MODE COMPARISON")
    print("="*60)

    mode_summary = df.groupby('accounting_mode').agg({
        'spend': 'sum',
        'attributed_rev': 'sum',
        'rev': 'sum',
        'transactions': 'sum',
        'visits': 'sum'
    }).round(2)

    for mode, row in mode_summary.iterrows():
        print(f"\n{mode.upper()}:")
        print(f"  Spend: ${row['spend']:,.2f}")
        if mode == 'Accrual performance':
            revenue = row['attributed_rev']
            print(f"  Attributed Revenue: ${revenue:,.2f}")
        else:
            revenue = row['rev']
            print(f"  Cash Revenue: ${revenue:,.2f}")
        roas = revenue / row['spend'] if row['spend'] > 0 else 0
        print(f"  ROAS: {roas:.2f}")
        print(f"  Transactions: {int(row['transactions'])}")
        print(f"  Visits: {int(row['visits'])}")

def identify_opportunities(channel_summary):
    """Identify growth opportunities and challenges (migrated)."""
    print("\n" + "="*60)
    print("🎯 OPPORTUNITIES & INSIGHTS")
    print("="*60)
    opportunities = []
    challenges = []
    for platform, row in channel_summary.iterrows():
        if row['spend'] == 0:
            continue
        roas = row['roas']
        cac = row['cac_1st_time'] if row['cac_1st_time'] > 0 else row['cac']
        spend = row['spend']
        if roas > 2.5 and spend > 1000:
            opportunities.append(f"🚀 SCALE UP: {platform} - Strong ROAS ({roas:.2f}) with significant spend (${spend:,.2f})")
        elif roas > 3.0 and spend < 1000:
            opportunities.append(f"💰 POTENTIAL: {platform} - Excellent ROAS ({roas:.2f}) but low spend (${spend:,.2f}) - consider increasing budget")
        if roas < 1.0 and spend > 500:
            challenges.append(f"⚠️ UNDERPERFORMING: {platform} - Poor ROAS ({roas:.2f}) with ${spend:,.2f} spend - needs optimization or pause")
        elif cac > 500 and roas > 0:
            challenges.append(f"💸 HIGH CAC: {platform} - CAC of ${cac:.2f} may be unsustainable")

    print("\n🌟 OPPORTUNITIES:")
    for opp in opportunities[:5]:
        print(f"  {opp}")
    print("\n⚠️ CHALLENGES:")
    for challenge in challenges[:5]:
        print(f"  {challenge}")
    if not opportunities:
        print("  📊 Consider testing new channels or optimizing existing campaigns")
    if not challenges:
        print("  ✅ No major performance issues identified")

def export_markdown_report(
    executive_metrics,
    channel_summary,
    campaign_analysis,
    revenue_only_df,
    first_time_metrics,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Generate the markdown report string.

    When *start_date* and *end_date* are provided, the headline and metadata
    reflect that explicit range instead of the script run-date.  This gives
    readers clarity about the actual data window when the most recent days
    are missing from the CSV export.
    """

    lines: list[str] = []

    if start_date and end_date:
        period_str = f"{start_date:%Y-%m-%d}–{end_date:%Y-%m-%d}"
        report_title_date = period_str
        desc_period = f"{start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}"
        report_date_meta = end_date.strftime("%Y-%m-%d")
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        report_title_date = today_str
        desc_period = f"7-day performance period ending {today_str}"
        report_date_meta = today_str

    lines.append("---")
    lines.append("title: \"Weekly Growth Report\"")
    lines.append(
        f"description: \"Weekly Growth Report for Eskiin covering {desc_period}\""
    )
    lines.append("recipient: \"Ingrid\"")
    lines.append("report_type: \"Weekly Growth Report\"")
    lines.append(f"date: {report_date_meta!r}")
    lines.append("period: \"7-Day Review\"")
    lines.append("---\n")
    lines.append(f"# Weekly Growth Report — {report_title_date}\n\n---\n")
    lines.append("## 1. Executive Summary\n")
    total_spend = executive_metrics['total_spend']
    total_revenue = executive_metrics['total_revenue']
    overall_roas = executive_metrics['overall_roas']
    overall_cac = executive_metrics['overall_cac']
    paid_df_exec = channel_summary[channel_summary['spend'] > 0]
    paid_spend_exec = paid_df_exec['spend'].sum()
    paid_revenue_exec = paid_df_exec['attributed_rev'].sum()
    paid_transactions_exec = paid_df_exec['transactions'].sum()
    paid_roas_exec = paid_revenue_exec / paid_spend_exec if paid_spend_exec else 0
    paid_cac_exec = paid_spend_exec / paid_transactions_exec if paid_transactions_exec else 0
    lines.append(
        (
            f"**Overall Performance**: Total DTC spend reached **${total_spend:,.0f}** "
            f"across all channels with **{overall_roas:.2f} ROAS**, generating "
            f"**${total_revenue:,.0f}** in revenue and blended **CAC of ${overall_cac:,.2f}**. "
            f"Paid Media delivered **${paid_revenue_exec:,.0f}** revenue at "
            f"**{paid_roas_exec:.2f} ROAS** with **CAC of ${paid_cac_exec:.2f}**, "
            f"across **{int(paid_transactions_exec)} transactions**. The business achieved "
            f"**{int(executive_metrics['total_transactions'])} total transactions** "
            f"during this 7-day period.\n\n"
        )
    )
    lines.append("## 2. DTC Performance — 7-Day Snapshot (Northbeam)\n")
    headers = [
        "Channel", "Period Spend", "% of Total", "CAC", "CAC 1st",
        "ROAS", "ROAS 1st", "AOV", "Transactions", "Revenue"
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["-" * len(h) for h in headers]) + "|")
    total_transactions = executive_metrics['total_transactions']
    overall_cac_1st = (
        total_spend / channel_summary['transactions_1st_time'].sum()
        if channel_summary['transactions_1st_time'].sum() > 0 else 0
    )
    lines.append(
        (
            f"| **All DTC** | **${total_spend:,.0f}** | **100%** | "
            f"**${overall_cac:,.2f}** | **${overall_cac_1st:.2f}** | "
            f"**{overall_roas:.2f}** | **{executive_metrics['overall_roas_1st_time']:.2f}** | "
            f"**${executive_metrics['overall_aov']:.0f}** | **{int(total_transactions)}** | "
            f"**${total_revenue:,.0f}** |"
        ))
    paid_df = channel_summary[channel_summary['spend'] > 0]
    if not paid_df.empty:
        paid_spend = paid_df['spend'].sum()
        paid_revenue = paid_df['attributed_rev'].sum()
        paid_revenue_1st = paid_df['attributed_rev_1st_time'].sum()
        paid_transactions = paid_df['transactions'].sum()
        paid_transactions_1st = paid_df['transactions_1st_time'].sum()
        paid_roas = paid_revenue / paid_spend if paid_spend else 0
        paid_roas_1st = paid_revenue_1st / paid_spend if paid_spend else 0
        paid_cac = paid_spend / paid_transactions if paid_transactions else 0
        paid_cac_1st = paid_spend / paid_transactions_1st if paid_transactions_1st else 0
        paid_aov = paid_revenue / paid_transactions if paid_transactions else 0
        percent_total_paid = paid_spend / total_spend * 100 if total_spend > 0 else 0
        lines.append(
            f"| **Paid Media** | ${paid_spend:,.0f} | {percent_total_paid:.1f}% | ${paid_cac:.2f} | ${paid_cac_1st:.2f} | {paid_roas:.2f} | {paid_roas_1st:.2f} | ${paid_aov:,.0f} | {int(paid_transactions)} | ${paid_revenue:,.0f} |")
    total_spend_safe = total_spend if total_spend != 0 else 1
    for platform, row in channel_summary.iterrows():
        spend = row['spend']
        if spend <= 0:
            continue
        percent_total = spend / total_spend_safe * 100
        lines.append(
            f"| {platform} | ${spend:,.0f} | {percent_total:.1f}% | ${row['cac']:.2f} | ${row['cac_1st_time']:.2f} | {row['roas']:.2f} | {row['roas_1st_time']:.2f} | ${row['aov']:,.0f} | {int(row['transactions'])} | ${row['attributed_rev']:,.0f} |")
    lines.append("\n---\n")
    if not campaign_analysis.empty:
        lines.append("## 3. Top Campaign Performance Analysis\n")
        subset_roas = campaign_analysis[campaign_analysis['roas'] > 0]
        idx = subset_roas.groupby('breakdown_platform_northbeam')['roas'].idxmax()
        top_roas = subset_roas.loc[idx].sort_values('roas', ascending=False)
        lines.append("### 🏆 Best Performing Campaigns by ROAS\n")
        headers2 = [
        "Platform", "Campaign Name", "ROAS", "ROAS 1st", "CAC",
        "CAC 1st", "AOV", "AOV 1st", "Spend", "Revenue"
    ]
        lines.append("| " + " | ".join(headers2) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers2]) + "|")
        if not top_roas.empty:
            tot_spend = top_roas['spend'].sum()
            tot_rev = top_roas['attributed_rev'].sum()
            tot_rev1 = top_roas.get('attributed_rev_1st_time', pd.Series(dtype=float)).sum()
            tot_txn = top_roas['transactions'].sum() if 'transactions' in top_roas.columns else 0
            tot_txn1 = top_roas.get('transactions_1st_time', pd.Series(dtype=float)).sum()
            tot_roas = tot_rev / tot_spend if tot_spend else 0
            tot_roas1 = tot_rev1 / tot_spend if tot_spend else 0
            tot_cac = tot_spend / tot_txn if tot_txn else 0
            tot_cac1 = tot_spend / tot_txn1 if tot_txn1 else 0
            tot_aov = tot_rev / tot_txn if tot_txn else 0
            tot_aov1 = tot_rev1 / tot_txn1 if tot_txn1 else 0
            lines.append(
                (
                    f"| **Totals** | — | **{tot_roas:.2f}** | {tot_roas1:.2f} | "
                    f"${tot_cac:.2f} | ${tot_cac1:.2f} | ${tot_aov:.2f} | "
                    f"${tot_aov1:.2f} | ${tot_spend:,.0f} | ${tot_rev:,.0f} |"
                ))
        for _, row in top_roas.iterrows():
            platform = row['breakdown_platform_northbeam']
            campaign = row['campaign_name'][:50].replace('|', '\\|')
            lines.append(
                (
                f"| {platform} | **{campaign}** | **{row['roas']:.2f}** | "
                f"{row.get('roas_1st_time', 0):.2f} | ${row.get('cac', 0):.2f} | "
                f"${row.get('cac_1st_time', 0):.2f} | ${row.get('aov', 0):.2f} | "
                f"${row.get('aov_1st_time', 0):.2f} | ${row['spend']:,.0f} | "
                f"${row['attributed_rev']:,.0f} |"
            ))
        agg_cols_sum = ['spend','attributed_rev','attributed_rev_1st_time','transactions','transactions_1st_time']
        for col in agg_cols_sum:
            if col not in campaign_analysis.columns:
                campaign_analysis[col] = 0
        aggregated = (
            campaign_analysis
            .groupby(['breakdown_platform_northbeam', 'campaign_name'], as_index=False)[agg_cols_sum]
            .sum()
        )
        aggregated['roas'] = (
            aggregated['attributed_rev'] /
            aggregated['spend'].replace({0: np.nan})
        )
        aggregated['roas_1st_time'] = (
            aggregated['attributed_rev_1st_time'] /
            aggregated['spend'].replace({0: np.nan})
        )
        aggregated['cac'] = (
            aggregated['spend'] /
            aggregated['transactions'].replace({0: np.nan})
        )
        aggregated['cac_1st_time'] = (
            aggregated['spend'] /
            aggregated['transactions_1st_time'].replace({0: np.nan})
        )
        aggregated['aov'] = (
            aggregated['attributed_rev'] /
            aggregated['transactions'].replace({0: np.nan})
        )
        aggregated['aov_1st_time'] = (
            aggregated['attributed_rev_1st_time'] /
            aggregated['transactions_1st_time'].replace({0: np.nan})
        )
        top_spend = aggregated.sort_values('spend', ascending=False).head(5)
        lines.append("\n### 💰 Highest Spend Campaigns\n")
        headers3 = [
        "Platform", "Campaign Name", "Spend", "ROAS", "ROAS 1st",
        "CAC", "CAC 1st", "AOV", "AOV 1st", "Revenue"
    ]
        lines.append("| " + " | ".join(headers3) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers3]) + "|")
        if not top_spend.empty:
            tot_spend2 = top_spend['spend'].sum()
            tot_rev2 = top_spend['attributed_rev'].sum()
            tot_rev1_2 = top_spend['attributed_rev_1st_time'].sum()
            tot_txn2 = top_spend['transactions'].sum()
            tot_txn1_2 = top_spend['transactions_1st_time'].sum()
            tot_roas2 = tot_rev2 / tot_spend2 if tot_spend2 else 0
            tot_roas1_2 = tot_rev1_2 / tot_spend2 if tot_spend2 else 0
            tot_cac2 = tot_spend2 / tot_txn2 if tot_txn2 else 0
            tot_cac1_2 = tot_spend2 / tot_txn1_2 if tot_txn1_2 else 0
            tot_aov2 = tot_rev2 / tot_txn2 if tot_txn2 else 0
            tot_aov1_2 = tot_rev1_2 / tot_txn1_2 if tot_txn1_2 else 0
            lines.append(
                f"| **Totals** | — | ${tot_spend2:,.0f} | {tot_roas2:.2f} | {tot_roas1_2:.2f} | ${tot_cac2:.2f} | ${tot_cac1_2:.2f} | ${tot_aov2:.2f} | ${tot_aov1_2:.2f} | ${tot_rev2:,.0f} |")
        for _, row in top_spend.iterrows():
            platform = row['breakdown_platform_northbeam']
            campaign = row['campaign_name'][:50].replace('|', '\\|')
            lines.append(
                f"| {platform} | **{campaign}** | ${row['spend']:,.0f} | {row['roas']:.2f} | {row.get('roas_1st_time', 0):.2f} | ${row.get('cac', 0):.2f} | ${row.get('cac_1st_time', 0):.2f} | ${row.get('aov', 0):.2f} | ${row.get('aov_1st_time', 0):.2f} | ${row['attributed_rev']:,.0f} |")
        exclude_platforms = {"Untattributed", "Excluded", "(not set)"}
        rev_filtered = revenue_only_df[~revenue_only_df['breakdown_platform_northbeam'].isin(exclude_platforms)]
        if not rev_filtered.empty:
            idx_rev = rev_filtered.groupby('breakdown_platform_northbeam')['attributed_rev'].idxmax()
            top_rev = rev_filtered.loc[idx_rev].sort_values('attributed_rev', ascending=False).head(10)
            lines.append("\n### 📧 Revenue-Only Campaigns ($0 Spend)\n")
            headers0 = ["Platform", "Campaign Name", "Revenue", "Transactions", "AOV"]
            lines.append("| " + " | ".join(headers0) + " |")
            lines.append("|" + "|".join(["-" * len(h) for h in headers0]) + "|")
            for _, row in top_rev.iterrows():
                platform = row['breakdown_platform_northbeam']
                campaign = row['campaign_name'][:50].replace('|','\\|')
                lines.append(f"| {platform} | **{campaign}** | ${row['attributed_rev']:,.0f} | {row['transactions']:.2f} | ${row.get('aov', 0):.2f} |")
            rev_tot = top_rev['attributed_rev'].sum()
            rev_txn_tot = top_rev['transactions'].sum()
            rev_aov_tot = rev_tot / rev_txn_tot if rev_txn_tot else 0
            lines.append(f"| **Totals** | — | ${rev_tot:,.0f} | {rev_txn_tot:.2f} | ${rev_aov_tot:.2f} |")
    if isinstance(channel_summary, pd.DataFrame) and not channel_summary.empty:
        lines.append("\n## 4. Channel Performance Metrics\n")
        headers_g = ["Channel", "Spend", "Revenue", "CAC", "ROAS", "AOV", "Transactions"]
        lines.append("| " + " | ".join(headers_g) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers_g]) + "|")
        high_spend = channel_summary[channel_summary['spend'] > 0].copy().sort_values('spend', ascending=False)
        rev_only = channel_summary[channel_summary['spend'] == 0].copy().sort_values('attributed_rev', ascending=False)
        combined = pd.concat([high_spend, rev_only])
        grand_spend = combined['spend'].sum()
        grand_rev = combined['attributed_rev'].sum()
        grand_txn = combined['transactions'].sum()
        grand_cac = grand_spend / grand_txn if grand_txn else 0
        grand_roas = grand_rev / grand_spend if grand_spend else 0
        grand_aov = grand_rev / grand_txn if grand_txn else 0
        lines.append(
            f"| **All Channels** | ${grand_spend:,.0f} | ${grand_rev:,.0f} | ${grand_cac:.2f} | {grand_roas:.2f} | ${grand_aov:.2f} | {int(grand_txn)} |")
        for platform, row in combined.iterrows():
            spend = row['spend']
            txns_raw = row['transactions']
            txns_display = f"{txns_raw:.2f}" if spend == 0 else f"{int(txns_raw)}"
            lines.append(
                f"| {platform} | ${spend:,.0f} | ${row['attributed_rev']:,.0f} | ${row['cac']:.2f} | {row['roas']:.2f} | ${row['aov']:.2f} | {txns_display} |")
    lines.append("\n---\n")
    lines.append(f"**Report Compiled**: {report_date_meta}\n")
    return "\n".join(lines)

# -------------------------------------------------------------
# 📅  Previous Week Utilities
# -------------------------------------------------------------

# Helper to pick newest file matching a pattern (used as fallback)
def _latest(pattern: str) -> str | None:
    matches = glob.glob(pattern, recursive=True)
    return max(matches, key=os.path.getmtime) if matches else None


def _find_previous_csv(stats_dir: str = "data/ads") -> str | None:
    """Return path to the previous-week CSV.

    Priority:
    1. Any file whose basename starts with ``prev-`` (Northbeam export you drop in).
    2. Otherwise, the *second* most-recent CSV in the directory.
    """
    csvs = sorted(glob.glob(os.path.join(stats_dir, "*.csv")), key=os.path.getmtime, reverse=True)
    for p in csvs:
        if os.path.basename(p).startswith("prev-"):
            return p
    if len(csvs) >= 2:
        return csvs[1]
    return None


def _load_csv_clean(path: str) -> pd.DataFrame | None:
    """Lightweight clone of base.load_and_clean_data() but non-interactive."""
    if not path or not os.path.exists(path):
        print("⚠️  Previous-week CSV not found – skipping deltas")
        return None
    df = pd.read_csv(path)

    # Minimal numeric cast
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
        "visits",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.fillna(0)
    # Ensure required platform col present
    if "breakdown_platform_northbeam" not in df.columns:
        df["breakdown_platform_northbeam"] = df.get("platform", "Unknown")
    return df


# -------------------------------------------------------------
# Δ  Delta Formatting Helpers
# -------------------------------------------------------------


def _pct_delta(cur: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (cur - prev) / prev * 100.0


def _fmt_delta(cur: float, prev: float, prefix: str = "$", digits: int = 0) -> str:
    """Return a formatted cell showing cur, prev and %Δ."""
    pct = _pct_delta(cur, prev)
    sign = "+" if pct > 0 else ("-" if pct < 0 else "")
    pct_str = f"{sign}{abs(pct):.0f}%"
    if prefix:
        cur_str = f"{prefix}{cur:,.{digits}f}"
        prev_str = f"{prefix}{prev:,.{digits}f}"
    else:
        cur_str = f"{cur:,.{digits}f}"
        prev_str = f"{prev:,.{digits}f}"
    return f"{cur_str} ( {prev_str} | {pct_str} )"


# -------------------------------------------------------------
# 🔎  Product & Category Mapping Helpers
# -------------------------------------------------------------

def load_product_mappings():
    """Load product mappings from the canonical product_data module."""
    # Use the canonical data directly
    product_to_category = product_data.PRODUCT_TO_CATEGORY.copy()
    # Ensure a default bucket for unmatched rows
    product_to_category.setdefault("Unattributed", "Unattributed")
    # Normalize helper
    def _norm(s: str):
        # insert spaces before CamelCase transitions first
        s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
        s = s.replace("_", " ").replace("-", " ")
        s = s.lower()
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # Use the pre-built aliases from product_data, but apply normalization
    alias_map = {_norm(k): v for k, v in product_data.ALIASES.items()}
    
    # Ensure canonical names map to themselves
    for prod in product_to_category:
        alias_map.setdefault(_norm(prod), prod)

    # Precompute variants with spaces removed for camel-case matches
    expanded_alias = {}
    for key, val in alias_map.items():
        expanded_alias[key] = val
        nospace = key.replace(" ", "")
        if nospace != key:
            expanded_alias.setdefault(nospace, val)

    # sort longest->shortest for deterministic greedy matching
    alias_sorted = sorted(expanded_alias.items(), key=lambda kv: len(kv[0]), reverse=True)
    return product_to_category, alias_sorted, _norm


def detect_product(row, alias_sorted, norm_fn):
    """Return canonical product found in Ad Name, Ad Set, then Campaign."""
    search_fields = ("ad_name", "adset_name", "campaign_name")
    for field in search_fields:
        original = str(row.get(field, ""))
        text_norm = norm_fn(original)
        text_nospace = text_norm.replace(" ", "")
        for alias, canonical in alias_sorted:
            if alias in text_norm or alias in text_nospace:
                return canonical
    return None


def assign_products(df: pd.DataFrame, alias_sorted, norm_fn):
    """Assign canonical product names to each row in the DataFrame.
    
    Args:
        df: DataFrame containing ad data
        alias_sorted: List of (alias, canonical) tuples sorted by alias length
        norm_fn: Function to normalize text for matching
        
    Returns:
        DataFrame with new 'product' column containing canonical product names
    """
    df = df.copy()
    df["product"] = df.apply(lambda r: detect_product(r, alias_sorted, norm_fn), axis=1)
    return df


def build_summary(df: pd.DataFrame, group_col: str):
    """Build a summary DataFrame with key metrics grouped by the specified column.

    Args:
        df: DataFrame containing ad data
        group_col: Column name to group by (e.g. 'product' or 'category')

    Returns:
        DataFrame with aggregated metrics and calculated ratios (ROAS, CAC, etc.)
    """
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
    ]
    present = [c for c in numeric_cols if c in df.columns]
    summary = df.groupby(group_col)[present].sum().astype(float)

    # Metric calculations
    summary["roas"] = (summary["attributed_rev"] / summary["spend"]).replace([np.inf], 0)
    summary["roas_1st_time"] = (
        summary["attributed_rev_1st_time"] / summary["spend"]
    ).replace([np.inf], 0)
    # Use *rounded* transactions for CAC / AOV to avoid confusing fractional counts
    txns_rounded = summary["transactions"].round().replace(0, np.nan)
    summary["cac"] = (summary["spend"] / txns_rounded).replace([np.inf], 0).fillna(0)
    summary["cac_1st_time"] = (
        summary["spend"] / summary["transactions_1st_time"].round().replace(0, np.nan)
    ).replace([np.inf], 0).fillna(0)
    summary["aov"] = (
        summary["attributed_rev"] / txns_rounded
    ).replace([np.inf], 0).fillna(0)

    # Store the rounded value for display purposes
    summary["transactions_display"] = txns_rounded.fillna(0)

    summary = summary.replace([np.inf, -np.inf], 0).round(2)
    summary = summary.sort_values("spend", ascending=False)
    return summary


def markdown_table(
    summary: pd.DataFrame,
    index_label: str,
    extra_col: str | None = None,
    prev_summary: pd.DataFrame | None = None,
):
    """Return a markdown table with optional Prev and Δ% columns for each metric."""

    headers: list[str] = [index_label]
    if extra_col:
        headers.append(extra_col)

    metrics = [
        ("spend", "$", 0, "Spend"),
        ("attributed_rev", "$", 0, "Revenue"),
        ("roas", "", 2, "ROAS"),
        ("roas_1st_time", "", 2, "ROAS 1st"),
        ("cac", "$", 2, "CAC"),
        ("cac_1st_time", "$", 2, "CAC 1st"),
        ("aov", "$", 2, "AOV"),
        ("transactions_display", "", 0, "Transactions"),
    ]

    for _, _, _, title in metrics:
        headers.append(title)
        if prev_summary is not None:
            headers.extend([f"{title} Prev", f"{title} Δ%"])

    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["-"] * len(headers)) + "|"]

    for idx, row in summary.iterrows():
        cells: list[str] = [idx]
        if extra_col:
            cells.append(str(row[extra_col]))

        for metric, prefix, dec, _ in metrics:
            cur_val = row[metric] if metric in row else 0
            # Current value
            cur_fmt = f"{prefix}{cur_val:,.{dec}f}" if prefix else f"{cur_val:,.{dec}f}" if dec else f"{int(cur_val)}"
            cells.append(cur_fmt)

            if prev_summary is not None:
                prev_val = prev_summary.loc[idx][metric] if idx in prev_summary.index and metric in prev_summary.columns else 0
                prev_fmt = f"{prefix}{prev_val:,.{dec}f}" if prefix else f"{prev_val:,.{dec}f}" if dec else f"{int(prev_val)}"
                pct = _pct_delta(cur_val, prev_val)
                sign = "+" if pct > 0 else ("-" if pct < 0 else "")
                delta_fmt = f"{sign}{abs(pct):.0f}%"
                cells.extend([prev_fmt, delta_fmt])

        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


# -------------------------------------------------------------
# Σ  Totals row helper specifically for CHANNEL table so that
#   WoW Prev and Δ columns can be displayed.
# -------------------------------------------------------------


def channel_totals_df(summary: pd.DataFrame, label: str = "**All Channels**") -> pd.DataFrame:
    """Return 1-row DataFrame with totals and rounded txns_display."""
    spend = summary["spend"].sum()
    revenue = summary["attributed_rev"].sum()
    txns = summary["transactions"].sum()

    txns_display = round(txns)
    rev_1st_sum = summary["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in summary.columns else 0
    txns_1st_sum = summary["transactions_1st_time"].sum() if "transactions_1st_time" in summary.columns else 0
    row = {
        "spend": spend,
        "attributed_rev": revenue,
        "roas": revenue / spend if spend else 0,
        "roas_1st_time": rev_1st_sum / spend if spend else 0,
        "cac": spend / txns_display if txns_display else 0,
        "cac_1st_time": spend / txns_1st_sum if txns_1st_sum else 0,
        "aov": revenue / txns_display if txns_display else 0,
        "transactions": txns_display,
        "transactions_display": txns_display,
    }
    return pd.DataFrame(row, index=[label])


# -------------------------------------------------------------
# Σ  Helper to add totals row
# -------------------------------------------------------------

def totals_row(summary: pd.DataFrame, label: str):
    """Return a one-row DataFrame with totals across the provided summary."""
    numeric_base = [
        "spend",
        "attributed_rev",
        "transactions",
    ]

    agg = summary[numeric_base].sum()
    spend = agg["spend"]
    revenue = agg["attributed_rev"]
    txns = agg["transactions"]

    txns_display = round(txns)

    rev_1st_sum = summary["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in summary.columns else 0
    txns_1st_sum = summary["transactions_1st_time"].sum() if "transactions_1st_time" in summary.columns else 0
    total_series = {
        "spend": spend,
        "attributed_rev": revenue,
        "roas": revenue / spend if spend else 0,
        "roas_1st_time": rev_1st_sum / spend if spend else 0,
        "cac": spend / txns_display if txns_display else 0,
        "cac_1st_time": spend / txns_1st_sum if txns_1st_sum else 0,
        "aov": revenue / txns_display if txns_display else 0,
        "transactions": txns_display,
        "transactions_display": txns_display,
    }

    return pd.DataFrame(total_series, index=[label])


# -------------------------------------------------------------
# 🏁  Main Routine
# -------------------------------------------------------------

def main():
    """Main entry point for the weekly report generation script.
    
    This function:
    1. Loads and cleans data from CSV files
    2. Analyzes channel performance
    3. Maps products and categories
    4. Generates markdown report with tables and metrics
    5. Saves report to data/reports/weekly directory
    """
    print("Eskiin Weekly Product/Category Report")
    print("========================================\n")

    # -------------------------------------------------------------
    # 🔧  CLI arguments (paths to current-year MTD CSVs)
    # -------------------------------------------------------------

    parser = argparse.ArgumentParser(description="Generate weekly growth report with YoY comparisons")
    parser.add_argument("--google_csv", help="Path to current Google Ads MTD CSV", default=None)
    parser.add_argument("--meta_csv", help="Path to current Meta Ads MTD CSV", default=None)
    args, _unknown = parser.parse_known_args()

    # Determine current-year MTD files (CLI arg if supplied, otherwise prompt)
    def _prompt_mtd(platform: str, cli_value: str | None):
        if cli_value:
            return cli_value
        pattern = f"*{platform.lower()}*mtd*csv"
        return select_csv_file(
            directory="data/ads",
            file_pattern=pattern,
            prompt_message=f"Select {platform} MTD CSV (or q to skip): ",
            max_items=10,
        )

    google_cur_path = _prompt_mtd("google", args.google_csv)
    meta_cur_path   = _prompt_mtd("meta",   args.meta_csv)

    # 1. Load channel-level cleaned data from the base module
    df = load_and_clean_data()
    if df is None:
        return

    # Preserve a copy of the *full* dataset before we potentially
    # slice it down to a specific date range so we can use it to
    # derive the previous-period DataFrame without re-prompting for
    # a file.
    df_full = df.copy()

    # -------------------------------------------------------------
    # 📅  Interactive date filtering (new)
    # -------------------------------------------------------------
    # If the loaded CSV now contains an explicit date column, allow
    # the user to choose a custom date window (e.g. the most recent
    # 7-day period) and automatically derive the *previous* period
    # for WoW comparisons from the *same* file.  If no usable date
    # column is found we fall back to the older behaviour that looks
    # for a separate "prev-" CSV on disk.
    # -------------------------------------------------------------

    # Identify potential date column(s) – case-insensitive match
    date_cols = [c for c in df.columns if c.lower() in {"date", "day", "report_date"}]
    use_date_filter = bool(date_cols)

    prev_df: pd.DataFrame | None = None  # will be populated below

    if use_date_filter:
        date_col = date_cols[0]
        # Ensure datetime dtype for both filtered and full copies
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df_full[date_col] = pd.to_datetime(df_full[date_col], errors="coerce")

        # --------------------------------------------------
        # ①  Select CURRENT period
        # --------------------------------------------------
        period_menu = (
            "Choose reporting period (Northbeam alignment):\n"
            "  1) Last 7 days\n"
            "  2) Last 14 days\n"
            "  3) Last 30 days\n"
            "  4) Custom range\n"
        )
        while True:
            choice = input(period_menu + "Selection: ").strip()
            if choice in {"1", "7", "last 7", "l7"}:
                days = 7
                break
            if choice in {"2", "14", "last 14", "l14"}:
                days = 14
                break
            if choice in {"3", "30", "last 30", "l30"}:
                days = 30
                break
            if choice in {"4", "custom", "c"}:
                days = None  # handled below
                break
            print("❌ Invalid option – try again.\n")

        if days is not None:
            # Determine the natural "end" of the dataset.
            # If the most-recent date equals *today* (script run-date),
            # step back one day because Northbeam's presets usually end on
            # the prior day.  Otherwise treat the max date in the file as
            # the period end.  This avoids off-by-one errors when the file
            # already stops at yesterday (the common case for exports).

            latest_dt = df_full[date_col].max().date()

            today = datetime.today().date()
            if latest_dt == today:
                end_date = latest_dt - timedelta(days=1)
            else:
                end_date = latest_dt
            start_date = end_date - timedelta(days=days - 1)
        else:
            # Custom range prompt
            while True:
                try:
                    start_input = input("Enter report START date  (YYYY-MM-DD): ").strip()
                    end_input   = input("Enter report END date    (YYYY-MM-DD): ").strip()
                    start_date = pd.to_datetime(start_input).date()
                    end_date   = pd.to_datetime(end_input).date()
                    if end_date < start_date:
                        print("❌ End date must not be before start date. Try again.\n")
                        continue
                    break
                except ValueError:
                    print("❌ Invalid date format – please use YYYY-MM-DD.\n")

        # Slice current period
        df = df[(df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)].copy()

        if df.empty:
            print("⚠️  No data found in the selected period – exiting.")
            return

        # --------------------------------------------------
        # ②  Select COMPARISON window
        # --------------------------------------------------
        compare_menu = (
            "Compare against:\n"
            "  1) Previous period (same length)\n"
            "  2) Previous month\n"
            "  3) Previous year\n"
            "  4) None\n"
        )
        while True:
            comp_choice = input(compare_menu + "Selection: ").strip()
            if comp_choice == "1":
                prev_start = start_date - timedelta(days=(end_date - start_date).days + 1)
                prev_end   = start_date - timedelta(days=1)
                break
            elif comp_choice == "2":
                prev_start = (start_date - pd.DateOffset(months=1)).date()
                prev_end   = (end_date   - pd.DateOffset(months=1)).date()
                break
            elif comp_choice == "3":
                prev_start = (start_date - pd.DateOffset(years=1)).date()
                prev_end   = (end_date   - pd.DateOffset(years=1)).date()
                break
            elif comp_choice == "4":
                prev_start = prev_end = None
                break
            else:
                print("❌ Invalid option – try again.\n")

        if prev_start and prev_end:
            prev_df_subset = df_full[(df_full[date_col].dt.date >= prev_start) & (df_full[date_col].dt.date <= prev_end)].copy()
            if prev_df_subset.empty:
                print("⚠️  No data found in the selected comparison window – skipping WoW comparisons.")
                prev_df = None
            else:
                prev_df = prev_df_subset

        # Announce selection summary
        label_prev = f"{prev_start} → {prev_end}" if prev_start else "NONE"
        print(f"📅 Current period : {start_date} → {end_date}\n" +
              f"🔁 Comparison     : {label_prev}\n")
    # -------------------------------------------------------------
    # Legacy behaviour – fall back to separate previous-week CSV
    # -------------------------------------------------------------
    else:
        prev_csv = _find_previous_csv()
        prev_df = _load_csv_clean(prev_csv) if prev_csv else None

    # -------------------------------------------------------------
    # 2️⃣  Product mapping & summary preparation (current period)
    # -------------------------------------------------------------

    product_to_category, alias_sorted, norm_fn = load_product_mappings()

    # Assign canonical product to each row
    df_prod = assign_products(df, alias_sorted, norm_fn)

    # Label rows with no matched product as 'Unattributed'
    df_prod["product"] = df_prod["product"].fillna("Unattributed")

    # --- Accrual rows (for unattributed + meta grouping logic later) ---
    accrual_df_prod = df_prod[df_prod["accounting_mode"] == "Accrual performance"].copy()

    def _is_blank(val):
        return pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "(no name)"

    # Flag campaign-summary rows (blank adset/ad names) and drop them when detailed rows exist
    accrual_df_prod["_is_summary"] = accrual_df_prod.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )
    has_detail = accrual_df_prod.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    accrual_filtered = accrual_df_prod[~(accrual_df_prod["_is_summary"] & has_detail)].copy()

    # --- Cash snapshot rows for CAC/AOV consistency ---
    cash_df_prod = df_prod[df_prod["accounting_mode"] == "Cash snapshot"].copy()
    cash_df_prod["_is_summary"] = cash_df_prod.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )
    cash_has_detail = cash_df_prod.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    cash_filtered = cash_df_prod[~(cash_df_prod["_is_summary"] & cash_has_detail)].copy()

    # Build summaries
    product_summary = build_summary(cash_filtered[cash_filtered["product"].notna()], "product")

    cash_filtered["category"] = cash_filtered["product"].map(product_to_category).fillna("Unattributed")
    category_summary = build_summary(cash_filtered[cash_filtered["category"].notna()], "category")

    # -------------------------------------------------------------
    # Previous-period mapping placeholders (will be filled if prev_df exists)
    # -------------------------------------------------------------

    # These summaries are not used in the current version
    # prev_product_summary = prev_category_summary = None

    if prev_df is not None:
        prev_df_prod = assign_products(prev_df, alias_sorted, norm_fn)
        prev_cash_df = prev_df_prod[prev_df_prod["accounting_mode"] == "Cash snapshot"].copy()
        prev_cash_df["category"] = prev_cash_df["product"].map(product_to_category).fillna("Unattributed")

        prev_product_summary = build_summary(prev_cash_df[prev_cash_df["product"].notna()], "product")
        prev_category_summary = build_summary(prev_cash_df[prev_cash_df["category"].notna()], "category")

    # -------------------------------------------------------------
    # 🚩 Capture Unattributed rows for alias discovery
    # -------------------------------------------------------------
    unattributed_df = accrual_filtered[accrual_filtered["product"] == "Unattributed"].copy()

    if not unattributed_df.empty:
        cols_to_keep = [
            "breakdown_platform_northbeam",
            "campaign_name",
            "adset_name",
            "ad_name",
            "spend",
            "attributed_rev",
        ]
        unattributed_export = unattributed_df[cols_to_keep].sort_values("spend", ascending=False)

        out_dir = Path("data/products/unattributed")
        out_dir.mkdir(parents=True, exist_ok=True)
        export_name = out_dir / f"unattributed_lines_{datetime.now().strftime('%Y-%m-%d')}.csv"
        unattributed_export.to_csv(export_name, index=False)
        print(f"📤 Exported {len(unattributed_export)} unattributed rows to {export_name}")

    # 4. Run existing channel-level analyses (for executive summary etc.)
    channel_summary = analyze_channel_performance(df)
    if channel_summary.empty:
        print("No channel data – exiting")
        return

    executive_metrics = generate_executive_summary(channel_summary)
    campaign_analysis, revenue_only_df = analyze_campaign_performance(df)
    first_time_metrics = analyze_first_time_metrics(df)
    analyze_attribution_modes(df)
    identify_opportunities(channel_summary)

    # 5. Assemble markdown report
    base_report = export_markdown_report(
        executive_metrics,
        channel_summary,
        campaign_analysis,
        revenue_only_df,
        first_time_metrics,
        start_date=start_date if 'start_date' in locals() else None,
        end_date=end_date if 'end_date' in locals() else None,
    )

    # Prepare product summary with Category column for display
    # Product display with totals row
    prod_display = product_summary.copy()
    prod_display["Category"] = prod_display.index.map(product_to_category)

    prod_tot = totals_row(prod_display, label="**All Products**")
    prod_tot["Category"] = "—"

    prod_table_df = pd.concat([prod_tot, prod_display])

    # Category display with totals row
    cat_tot = totals_row(category_summary, label="**All Categories**")
    category_table_df = pd.concat([cat_tot, category_summary])

    product_section_md = (
        "\n## 2a. Performance by Product (Cash Snapshot)\n" +
        markdown_table(prod_table_df, index_label="Product", extra_col="Category") +
        "\n\n## 2b. Performance by Category (Cash Snapshot)\n" +
        markdown_table(category_table_df, index_label="Category") +
        "\n---\n"
    )

    # -------------------------------------------------------------
    # 🚀 Meta Product Group Performance (Accrual Performance)
    # -------------------------------------------------------------
    meta_base = df[(df["accounting_mode"] == "Accrual performance") &
                   (df["breakdown_platform_northbeam"].astype(str).str.contains(r"meta|facebook|fb|instagram", case=False, na=False))].copy()

    # Remove campaign summary rows to avoid double-counting (same logic as above)
    def _is_blank(val):
        return pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "(no name)"

    meta_base["_is_summary"] = meta_base.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )
    has_meta_detail = meta_base.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    meta_accrual = meta_base[~(meta_base["_is_summary"] & has_meta_detail)].copy()

    if not meta_accrual.empty:
        # Use campaign-name keywords for grouping to align with user's totals
        def _keyword_group(row):
            text = str(row.get("campaign_name", "")).lower()
            # Explicit keywords checked in priority order to avoid mis-classification
            if "bundle" in text:
                return "Bundle"
            if "blanket" in text:
                return "Sauna Blanket"
            if "pemf" in text:
                return "PEMF Mat"
            if "hat" in text:
                return "Red Light Hat"
            if "mask" in text:
                return "Red Light Mask"
            return "Body Care & Supplements"

        meta_accrual["product_group"] = meta_accrual.apply(_keyword_group, axis=1)

        # Ensure groups exactly match the desired order for table output
        desired_order = [
            "Body Care & Supplements",
            "Sauna Blanket",
            "Red Light Hat",
            "PEMF Mat",
            "Red Light Mask",
            "Bundle",
        ]

        meta_group_df = meta_accrual.copy()

        meta_summary = build_summary(meta_group_df, "product_group")

        # Re-index to ensure all groups appear (missing groups will be 0)
        meta_summary = meta_summary.reindex(desired_order).fillna(0)

        # Build markdown table mirroring DTC metrics
        headers = [
            "Product Group",
            "Spend",
            "% of Total",
            "CAC",
            "CAC 1st",
            "ROAS",
            "ROAS 1st",
            "AOV",
            "Transactions",
            "Revenue",
        ]
        meta_lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["-"] * len(headers)) + "|"]

        total_spend_meta = meta_summary["spend"].sum() if not meta_summary.empty else 0

        for idx, row in meta_summary.iterrows():
            spend = row["spend"]
            pct_total = (spend / total_spend_meta * 100) if total_spend_meta else 0
            meta_lines.append(
                f"| {idx} | ${spend:,.0f} | {pct_total:.1f}% | "
                f"${row['cac']:,.2f} | ${row['cac_1st_time']:,.2f} | "
                f"{row['roas']:.2f} | {row['roas_1st_time']:.2f} | "
                f"${row['aov']:,.0f} | {int(row['transactions_display'])} | "
                f"${row['attributed_rev']:,.0f} |"
            )

        meta_section_md = (
            "\n## 2c. Meta Product Group Performance (Accrual Performance)\n" +
            "\n".join(meta_lines) +
            "\n---\n"
        )
    else:
        meta_section_md = ""

    # -------------------------------------------------------------
    # 🔄 Build DTC channel table with WoW columns
    # -------------------------------------------------------------
    # Only keep channels with spend > 0 for display, but compute the
    # totals row using the full data so revenue-only rows are still
    # included in the aggregate metrics.

    channel_summary["transactions_display"] = channel_summary["transactions"].round()

    # Build display DF: totals row + channels with spend > 0
    chan_tot = channel_totals_df(channel_summary)
    channel_nonzero = channel_summary[channel_summary["spend"] > 0].copy()
    # Insert a consolidated **Paid Media** row (all channels with spend)
    paid_tot = totals_row(channel_nonzero, label="**Paid Media**")
    channel_summary_display = pd.concat([chan_tot, paid_tot, channel_nonzero])

    prev_channel_summary = None
    if prev_df is not None:
        prev_channel_summary_full = analyze_channel_performance(prev_df)
        if isinstance(prev_channel_summary_full, pd.DataFrame) and not prev_channel_summary_full.empty:
            prev_channel_summary_full["transactions_display"] = prev_channel_summary_full["transactions"].round()
            prev_tot = channel_totals_df(prev_channel_summary_full)
            prev_nonzero = prev_channel_summary_full[prev_channel_summary_full["spend"] > 0].copy()
            prev_paid_tot = totals_row(prev_nonzero, label="**Paid Media**")
            prev_channel_summary = pd.concat([prev_tot, prev_paid_tot, prev_nonzero])

    dtc_table_md = "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)\n" + \
        markdown_table(channel_summary_display, index_label="Channel", prev_summary=prev_channel_summary) + "\n"

    # ----------------------------------------------
    # 📝  Build the final markdown by starting from
    #     the base report, renaming the DTC header,
    #     and inserting the Product & Category tables
    #     directly beneath that section (as 2a/2b).
    # ----------------------------------------------

    final_report = base_report  # start fresh from base

    # 1) Rename key section headers so we can reliably locate them
    header_map = {
        "## 2. DTC Performance — 7-Day Snapshot (Northbeam)": "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)",
        "## 3. Top Campaign Performance Analysis": "## 3. Top Campaign Performance Analysis (Accrual Performance)",
        "## 4. Channel Performance Metrics": "## 4. Channel Performance Metrics (Accrual Performance)",
    }
    for old, new in header_map.items():
        final_report = final_report.replace(old, new)

    # 2) Replace the existing DTC table with the enhanced version that
    #    includes WoW deltas, then append the Product (2a) & Category (2b)
    #    tables directly afterwards.
    dtc_header = "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)"
    hdr_pos = final_report.find(dtc_header)
    if hdr_pos != -1:
        divider_pos = final_report.find("\n---\n", hdr_pos)
        if divider_pos != -1:
            final_report = (
                final_report[:hdr_pos] +
                dtc_table_md + "\n" + product_section_md + meta_section_md +
                final_report[divider_pos:]
            )
        else:
            # Fallback – no divider found; replace from header line to next blank line
            next_break = final_report.find("\n\n", hdr_pos)
            replace_end = next_break if next_break != -1 else hdr_pos
            final_report = (
                final_report[:hdr_pos] +
                dtc_table_md + "\n" + product_section_md + meta_section_md +
                final_report[replace_end:]
            )
    else:
        # If header somehow missing, append both sections to ensure they appear.
        final_report += "\n" + dtc_table_md + "\n" + product_section_md + meta_section_md

    # -------------------------------------------------------------
    # 📈 Week-over-Week Executive Delta Overview (re-injected)
    # -------------------------------------------------------------
    if prev_df is not None:
        cur_acc = df[df["accounting_mode"] == "Accrual performance"].copy()
        prev_acc = prev_df[prev_df["accounting_mode"] == "Accrual performance"].copy()

        def _totals(d):
            return {
                "spend": d["spend"].sum(),
                "rev": d["attributed_rev"].sum(),
                "txns": d["transactions"].sum(),
                # First-time metrics (may be absent in some exports)
                "rev_1st": d["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in d.columns else 0,
                "txns_1st": d["transactions_1st_time"].sum() if "transactions_1st_time" in d.columns else 0,
            }

        tot_cur = _totals(cur_acc)
        tot_prev = _totals(prev_acc)
        # Derived metrics
        tot_cur["roas"] = tot_cur["rev"] / tot_cur["spend"] if tot_cur["spend"] else 0
        tot_prev["roas"] = tot_prev["rev"] / tot_prev["spend"] if tot_prev["spend"] else 0
        # First-time ROAS & CAC
        tot_cur["roas_1st"] = (
            tot_cur["rev_1st"] / tot_cur["spend"] if tot_cur["spend"] else 0
        )
        tot_prev["roas_1st"] = (
            tot_prev["rev_1st"] / tot_prev["spend"] if tot_prev["spend"] else 0
        )
        tot_cur["cac_1st"] = (
            tot_cur["spend"] / tot_cur["txns_1st"] if tot_cur["txns_1st"] else 0
        )
        tot_prev["cac_1st"] = (
            tot_prev["spend"] / tot_prev["txns_1st"] if tot_prev["txns_1st"] else 0
        )

        wow_lines = [
            "\n### Week-over-Week Overview\n",
            f"* **Spend:** {_fmt_delta(tot_cur['spend'], tot_prev['spend'])}",
            f"* **Revenue:** {_fmt_delta(tot_cur['rev'], tot_prev['rev'])}",
            f"* **ROAS:** {_fmt_delta(tot_cur['roas'], tot_prev['roas'], prefix='', digits=2)}",
            f"* **ROAS 1st:** {_fmt_delta(tot_cur['roas_1st'], tot_prev['roas_1st'], prefix='', digits=2)}",
            f"* **CAC 1st:** {_fmt_delta(tot_cur['cac_1st'], tot_prev['cac_1st'], prefix='$', digits=2)}",
            f"* **Transactions:** {_fmt_delta(tot_cur['txns'], tot_prev['txns'], prefix='', digits=0)}",
            "\n",
        ]

        exec_hdr = "## 1. Executive Summary"
        pos_exec = final_report.find(exec_hdr)
        if pos_exec != -1:
            insert_pos = final_report.find("\n", pos_exec + len(exec_hdr)) + 1
            final_report = final_report[:insert_pos] + "\n".join(wow_lines) + final_report[insert_pos:]

        # --------------------------------------------------
        # 📝  Replace the single-line Overall Performance
        #     sentence with a version that includes the
        #     current + prev values and %Δ for the four
        #     headline metrics (Spend, Revenue, ROAS, CAC).
        # --------------------------------------------------

        try:
            # Build delta-formatted strings
            spend_fmt   = _fmt_delta(tot_cur["spend"], tot_prev["spend"], prefix="$", digits=0)
            rev_fmt     = _fmt_delta(tot_cur["rev"],   tot_prev["rev"],   prefix="$", digits=0)
            roas_fmt    = _fmt_delta(tot_cur["roas"],  tot_prev["roas"],  prefix="",  digits=2)

            # Blended CAC (all transactions)
            tot_cur["cac_blend"]  = tot_cur["spend"] / tot_cur["txns"] if tot_cur["txns"] else 0
            tot_prev["cac_blend"] = tot_prev["spend"] / tot_prev["txns"] if tot_prev["txns"] else 0
            cac_fmt    = _fmt_delta(tot_cur["cac_blend"], tot_prev["cac_blend"], prefix="$", digits=2)

            overall_line_new = (
                f"**Overall Performance**: Total DTC spend reached **{spend_fmt}** across all channels with **{roas_fmt} ROAS**, "
                f"generating **{rev_fmt}** in revenue and blended **CAC of {cac_fmt}**."
            )

            try:
                # Use re module imported at the top
                # Replace entire Overall Performance paragraph (until double newline)
                final_report = re.sub(r"\*\*Overall Performance\*\*[\s\S]*?\n\n", overall_line_new + "\n\n", final_report, count=1)
            except (ValueError, AttributeError) as _e:
                # If string formatting fails, keep the original sentence
                pass

            # Previous-year daily exports – locate dynamically **within
            # data/ads/** (recursive) so we match the executive report's
            # behaviour and avoid hard-coded paths.

            ads_root = os.path.join("data", "ads")  # base directory for ad exports
            google_prev_path = _latest(os.path.join(ads_root, "**", "google-2024*-daily*.csv"))
            if not google_prev_path:
                # Fallback: any Google 2024 daily export CSV
                google_prev_path = _latest(os.path.join(ads_root, "**", "google-*2024*.csv"))

            meta_prev_path   = _latest(os.path.join(ads_root, "**", "meta-*2024*export*.csv"))
            if not meta_prev_path:
                # Fallback: any Meta 2024 daily export CSV
                meta_prev_path = _latest(os.path.join(ads_root, "**", "meta-*2024*.csv"))

            def _summarize_google(cur_path: str | None, prev_path: str):
                """Return dict with spend, revenue, conversions, roas for current & previous year MTD."""
                if not cur_path or not prev_path or not os.path.exists(cur_path) or not os.path.exists(prev_path):
                    return None

                cur_df = pd.read_csv(cur_path, skiprows=2, thousands=",")
                prev_df = pd.read_csv(prev_path, skiprows=2, thousands=",")

                cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
                prev_df["Day"] = pd.to_datetime(prev_df["Day"], errors="coerce")

                if cur_df["Day"].isna().all() or prev_df["Day"].isna().all():
                    return None

                end_cur = cur_df["Day"].max()
                start_cur = end_cur - timedelta(days=6)  # Last 7 days inclusive
                end_prev = datetime(end_cur.year - 1, end_cur.month, end_cur.day)
                start_prev = end_prev - timedelta(days=6)

                cur_mtd = cur_df[(cur_df["Day"] >= start_cur) & (cur_df["Day"] <= end_cur)].copy()
                prev_mtd = prev_df[(prev_df["Day"] >= start_prev) & (prev_df["Day"] <= end_prev)].copy()

                for col in ["Cost", "Conv. value", "Conversions"]:
                    cur_mtd[col] = pd.to_numeric(cur_mtd[col], errors="coerce")
                    prev_mtd[col] = pd.to_numeric(prev_mtd[col], errors="coerce")

                def _tot(df):
                    return (
                        df["Cost"].sum(),
                        df["Conv. value"].sum(),
                        df["Conversions"].sum(),
                    )

                spend_cur, rev_cur, conv_cur = _tot(cur_mtd)
                spend_prev, rev_prev, conv_prev = _tot(prev_mtd)

                roas_cur = rev_cur / spend_cur if spend_cur else 0
                roas_prev = rev_prev / spend_prev if spend_prev else 0

                cpa_cur = spend_cur / conv_cur if conv_cur else 0
                cpa_prev = spend_prev / conv_prev if conv_prev else 0

                return {
                    "spend_cur": spend_cur,
                    "spend_prev": spend_prev,
                    "rev_cur": rev_cur,
                    "rev_prev": rev_prev,
                    "conv_cur": conv_cur,
                    "conv_prev": conv_prev,
                    "roas_cur": roas_cur,
                    "roas_prev": roas_prev,
                    "cpa_cur": cpa_cur,
                    "cpa_prev": cpa_prev,
                    "start_date": start_cur.strftime("%B %d"),
                    "end_date": end_cur.strftime("%B %d"),
                }

            def _summarize_meta(cur_path: str | None, prev_path: str):
                """Return dict with spend, revenue, conversions, roas for current & previous year MTD."""
                if not cur_path or not prev_path or not os.path.exists(cur_path) or not os.path.exists(prev_path):
                    return None

                cur_df = pd.read_csv(cur_path, thousands=",")
                prev_df = pd.read_csv(prev_path, thousands=",")

                cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
                prev_df["Day"] = pd.to_datetime(prev_df["Day"], errors="coerce")

                if cur_df["Day"].isna().all() or prev_df["Day"].isna().all():
                    return None

                end_cur = cur_df["Day"].max()
                start_cur = end_cur - timedelta(days=6)
                end_prev = datetime(end_cur.year - 1, end_cur.month, end_cur.day)
                start_prev = end_prev - timedelta(days=6)

                cur_mtd = cur_df[(cur_df["Day"] >= start_cur) & (cur_df["Day"] <= end_cur)].copy()
                prev_mtd = prev_df[(prev_df["Day"] >= start_prev) & (prev_df["Day"] <= end_prev)].copy()

                for col in ["Amount spent (USD)", "Purchases conversion value", "Purchases"]:
                    cur_mtd[col] = pd.to_numeric(cur_mtd[col], errors="coerce")
                    prev_mtd[col] = pd.to_numeric(prev_mtd[col], errors="coerce")

                def _tot(df):
                    return (
                        df["Amount spent (USD)"].sum(),
                        df["Purchases conversion value"].sum(),
                        df["Purchases"].sum(),
                    )

                spend_cur, rev_cur, conv_cur = _tot(cur_mtd)
                spend_prev, rev_prev, conv_prev = _tot(prev_mtd)

                roas_cur = rev_cur / spend_cur if spend_cur else 0
                roas_prev = rev_prev / spend_prev if spend_prev else 0

                cpa_cur = spend_cur / conv_cur if conv_cur else 0
                cpa_prev = spend_prev / conv_prev if conv_prev else 0

                return {
                    "spend_cur": spend_cur,
                    "spend_prev": spend_prev,
                    "rev_cur": rev_cur,
                    "rev_prev": rev_prev,
                    "conv_cur": conv_cur,
                    "conv_prev": conv_prev,
                    "roas_cur": roas_cur,
                    "roas_prev": roas_prev,
                    "cpa_cur": cpa_cur,
                    "cpa_prev": cpa_prev,
                    "start_date": start_cur.strftime("%B %d"),
                    "end_date": end_cur.strftime("%B %d"),
                }

            google_yoy = _summarize_google(google_cur_path, google_prev_path)
            meta_yoy = _summarize_meta(meta_cur_path, meta_prev_path)

            def _fmt(val: float, prefix: str = "$", digits: int = 0):
                if prefix:
                    return f"{prefix}{val:,.{digits}f}"
                return f"{val:,.{digits}f}"

            yoy_lines: list[str] = []
            if google_yoy and meta_yoy:
                end_label = google_yoy["end_date"]
                yoy_lines = [
                    f"\n## 5. Year-over-Year Growth (Week {google_yoy['start_date']}–{end_label})\n",
                ]

            def _yoy_rows(platform: str, data: dict[str, float]):
                rows: list[str] = []
                metrics = [
                    ("spend", "$", 0, "Spend"),
                    ("rev", "$", 0, "Revenue"),
                    ("conv", "", 0, "Conversions"),
                    ("roas", "", 2, "ROAS"),
                    ("cpa", "$", 2, "CPA"),
                ]
                rows.append(f"\n### {platform}\n")
                rows.append("| Metric | 2025 | 2024 | YoY Δ% |")
                rows.append("|-|-|-|-|")
                for key, prefix, digits, title in metrics:
                    cur_val = data[f"{key}_cur"]
                    prev_val = data[f"{key}_prev"]
                    pct = _pct_delta(cur_val, prev_val)
                    sign = "+" if pct > 0 else ("-" if pct < 0 else "")
                    delta_fmt = f"{sign}{abs(pct):.0f}%"
                    rows.append(
                        f"| {title} | {_fmt(cur_val, prefix, digits)} | {_fmt(prev_val, prefix, digits)} | {delta_fmt} |")
                return "\n".join(rows)

            if google_yoy:
                yoy_lines.append(_yoy_rows("Google Ads", google_yoy))
            if meta_yoy:
                yoy_lines.append(_yoy_rows("Meta Ads", meta_yoy))

            yoy_section_md = "\n".join(yoy_lines) + "\n"

            final_report += yoy_section_md

            # --------------------------------------------------
            # ✍️  Inject brief YoY summary sentences into the
            #     Executive Summary so that the markdown has a
            #     narrative statement, not just tables.
            # --------------------------------------------------

            try:
                def _pct(cur, prev):
                    if prev == 0:
                        return "0%"
                    d = (cur - prev) / prev * 100
                    return f"{d:+.0f}%".replace("+","+ ").replace("-","– ")

                if google_yoy and meta_yoy:
                    g_spd = _pct(google_yoy["spend_cur"], google_yoy["spend_prev"])
                    g_rev = _pct(google_yoy["rev_cur"],  google_yoy["rev_prev"])
                    m_spd = _pct(meta_yoy["spend_cur"],   meta_yoy["spend_prev"])
                    m_rev = _pct(meta_yoy["rev_cur"],     meta_yoy["rev_prev"])

                    yoy_summary = (
                        f"**Year-over-Year Highlights**: Google Ads spend {g_spd} vs 2024 with revenue {g_rev}; "
                        f"Meta Ads spend {m_spd} with revenue {m_rev}."
                    )

                    # Inject after Overall Performance paragraph (two consecutive newlines)
                    exec_hdr = "## 1. Executive Summary"
                    pos_exec = final_report.find(exec_hdr)
                    if pos_exec != -1:
                        para_end = final_report.find("\n\n", pos_exec)
                        if para_end != -1:
                            insert_pos = para_end + 2
                            if yoy_summary not in final_report:
                                final_report = final_report[:insert_pos] + yoy_summary + "\n\n" + final_report[insert_pos:]
                    
                    # (No further action required – YoY summary injected)
            except Exception:
                pass
        except (FileNotFoundError, pd.errors.EmptyDataError) as e:
            print(f"⚠️  YoY section failed - data loading error: {e}")
        except (KeyError, ValueError, AttributeError) as e:
            print(f"⚠️  YoY section failed - data processing error: {e}")

    # -------------------------------------------------------------
    # 📝  Initialize the working markdown document
    #       Start with the base report produced by the core script and
    #       immediately append the Product & Category section we built
    #       above.  Subsequent steps will mutate this `final_report`
    #       string in-place (e.g., replace the old DTC table, inject
    #       WoW overview, add appendix).
    # -------------------------------------------------------------

    # Replace existing DTC section with new one
    # final_report = base_report + product_section_md

    # Label major base-report tables as Accrual Performance to distinguish from cash snapshot
    header_map = {
        "## 2. DTC Performance — 7-Day Snapshot (Northbeam)": "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)",
        "## 3. Top Campaign Performance Analysis": "## 3. Top Campaign Performance Analysis (Accrual Performance)",
        "## 4. Channel Performance Metrics": "## 4. Channel Performance Metrics (Accrual Performance)",
        "### 💰 Highest Spend Campaigns": "### 💰 Highest Spend Campaigns",
    }
    for old, new in header_map.items():
        final_report = final_report.replace(old, new)

    # Append an appendix listing top unattributed campaigns for quick reference
    if not unattributed_df.empty:
        # Include all unattributed rows *with spend > 0*, sorted by spend descending
        top_unattributed = (
            unattributed_df[unattributed_df["spend"] > 0]
            .sort_values("spend", ascending=False)
        )
        appendix_lines = [
            "\n## Appendix: Top Unattributed Spend (Review for New Aliases)\n",
            "| Platform | Campaign | Ad Set | Ad | Spend | Revenue |",
            "|-|-|-|-|-|-|",
        ]

        # Helper to escape pipe characters that would break Markdown tables
        def _escape_pipes(text: str) -> str:
            """Return text safe for Markdown table cells by escaping pipe characters."""
            return str(text).replace("|", "\\|")

        for _, row in top_unattributed.iterrows():
            appendix_lines.append(
                f"| {row['breakdown_platform_northbeam']} | "
                f"{_escape_pipes(row['campaign_name'])[:40]} | "
                f"{_escape_pipes(row['adset_name'])[:30]} | "
                f"{_escape_pipes(row['ad_name'])[:30]} | "
                f"${row['spend']:,.0f} | ${row['attributed_rev']:,.0f} |")

        # Add totals row
        # Totals should reflect only the rows shown in the table
        tot_spend_un = top_unattributed['spend'].sum()
        tot_rev_un = top_unattributed['attributed_rev'].sum()
        appendix_lines.append(
            f"| **Totals** | — | — | — | **${tot_spend_un:,.0f}** | **${tot_rev_un:,.0f}** |")

        final_report += "\n".join(appendix_lines)

    # ------------------------------------------------------------------
    # 🗄️  Save report to dedicated output directory (data/reports/weekly)
    # ------------------------------------------------------------------
    report_dir = Path("data/reports/weekly")
    report_dir.mkdir(parents=True, exist_ok=True)

    out_file = report_dir / f"weekly-growth-report-with-products-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_report)

    print(f"📝 Markdown report saved to {out_file}")


if __name__ == "__main__":
    main()
