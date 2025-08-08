#!/usr/bin/env python3
"""
H1 Growth Report (Jan–Jun)

This script generates a half-year (H1) performance report that mirrors the weekly
report layout but aggregates metrics for the first six months of the current
year (Jan 1 → Jun 30) and compares Google & Meta platform exports to the same
period of the previous year.  Northbeam did not exist last year so channel-
level YoY deltas are not computed – only current-year Northbeam data are shown.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import weekly as base  # Re-use helpers now centralized here
from .weekly import (
    load_product_mappings,
    assign_products,
    build_summary,
    markdown_table,
    totals_row,
)


# -------------------------------------------------------------
# 🔧 CLI / default paths
# -------------------------------------------------------------

H1_MONTH_END = "06-30"  # YYYY-06-30 marks end of H1

# Base directory containing H1-report CSVs (moved under data/ads in repo restructure)
DEFAULT_DIR = Path("data/ads/h1-report")

# GA → Channel mapping keywords (very simple heuristics – tweak as needed)
GA_CHANNEL_KEYWORDS = {
    "google": "Google",
    "bing": "Microsoft Ads",
    "microsoft": "Microsoft Ads",
    "facebook": "Meta (Facebook)",
    "meta": "Meta (Facebook)",
    "instagram": "Meta (Facebook)",
    "tiktok": "TikTok",
    "aw": "Awin",        # awin sometimes appears as "aw" in source/medium
    "awin": "Awin",
    "shopmyshelf": "ShopMyShelf",
    "app": "AppLovin",   # applovin strings are long – "app" catch
    "lovin": "AppLovin",
    "pinterest": "Pinterest",
    # --- NEW email / sms / other organic & referral patterns ---
    "klaviyo": "Klaviyo",
    "attentive": "Attentive",
    "email": "Other Email",
    "sms": "Attentive",
    "linktree": "LinkTree",
    "youtube": "YouTube Organic",
    "reddit": "Reddit",
    "twitter": "Twitter",
}

# Unified alias map to convert GA channel names → Northbeam names
CHANNEL_ALIAS = {
    "Meta (Facebook)": "Facebook Ads",
    "Google": "Google Ads",
    "Microsoft Ads": "Microsoft Ads",  # same
}

def _apply_alias(sess_map: dict[str, float]) -> dict[str, float]:
    """Return new dict with channel names converted per CHANNEL_ALIAS."""
    out: dict[str, float] = {}
    for k, v in sess_map.items():
        norm = CHANNEL_ALIAS.get(k, k)
        out[norm] = out.get(norm, 0) + v
    return out

# Channels that will be merged into a unified Affiliate line
AFFILIATE_CANONICALS = {"awin", "shopmyshelf", "shareasale", "affiliate", "influencer"}

def _is_affiliate_channel(name: str) -> bool:
    """Return True if channel name should roll up into Affiliate bucket."""
    key = name.lower().replace(" ", "")
    return key in AFFILIATE_CANONICALS


# -------------------------------------------------------------
# 📄  Loading helpers
# -------------------------------------------------------------

def _load_nb(path: Path | str) -> pd.DataFrame:
    """Load Northbeam date-level export and coerce numeric columns."""
    if not path or not Path(path).exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, parse_dates=["date"], low_memory=False)

    # Keep only required numeric cols for aggregation
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.fillna(0)

    if "breakdown_platform_northbeam" not in df.columns:
        df["breakdown_platform_northbeam"] = df.get("platform", "Unknown")

    return df


def _filter_h1(df: pd.DataFrame, year: int) -> pd.DataFrame:
    start = pd.Timestamp(f"{year}-01-01")
    end = pd.Timestamp(f"{year}-{H1_MONTH_END}")
    return df[(df["date"] >= start) & (df["date"] <= end)].copy()


# -------------------------------------------------------------
# 📈 Platform YoY helpers (Google / Meta)
# -------------------------------------------------------------

def _summarize_google(path: Path | str) -> dict[str, float]:
    cur_df = pd.read_csv(path, skiprows=2, thousands=",")
    cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
    cur_df = cur_df.dropna(subset=["Day"])

    # Trim to H1 window for the file's year
    yr = cur_df["Day"].dt.year.mode()[0]
    h1_df = cur_df[(cur_df["Day"] >= f"{yr}-01-01") & (cur_df["Day"] <= f"{yr}-{H1_MONTH_END}")]

    for col in ["Cost", "Conv. value", "Conversions"]:
        h1_df[col] = pd.to_numeric(h1_df[col], errors="coerce")

    spend = h1_df["Cost"].sum()
    rev = h1_df["Conv. value"].sum()
    conv = h1_df["Conversions"].sum()
    roas = rev / spend if spend else 0
    cpa = spend / conv if conv else 0

    return {
        "spend": spend,
        "rev": rev,
        "conv": conv,
        "roas": roas,
        "cpa": cpa,
    }


def _summarize_meta(path: Path | str) -> dict[str, float]:
    cur_df = pd.read_csv(path, thousands=",")
    cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
    cur_df = cur_df.dropna(subset=["Day"])
    yr = cur_df["Day"].dt.year.mode()[0]
    h1_df = cur_df[(cur_df["Day"] >= f"{yr}-01-01") & (cur_df["Day"] <= f"{yr}-{H1_MONTH_END}")]

    for col in ["Amount spent (USD)", "Purchases conversion value", "Purchases"]:
        h1_df[col] = pd.to_numeric(h1_df[col], errors="coerce")

    spend = h1_df["Amount spent (USD)"].sum()
    rev = h1_df["Purchases conversion value"].sum()
    conv = h1_df["Purchases"].sum()
    roas = rev / spend if spend else 0
    cpa = spend / conv if conv else 0

    return {
        "spend": spend,
        "rev": rev,
        "conv": conv,
        "roas": roas,
        "cpa": cpa,
    }


# -------------------------------------------------------------
# 📄  Google Analytics loader
# -------------------------------------------------------------


def _load_ga_sessions(path: Path | str) -> dict[str, float]:
    """Return mapping of Northbeam-channel → sessions using simple keyword mapping."""
    if not path or not Path(path).exists():
        return {}

    # Skip comment lines starting with '#'
    ga_df = pd.read_csv(path, comment="#", thousands=",")
    ga_df.columns = [c.strip() for c in ga_df.columns]
    if "Session source / medium" not in ga_df.columns or "Sessions" not in ga_df.columns:
        return {}

    ga_df["Sessions"] = pd.to_numeric(ga_df["Sessions"], errors="coerce").fillna(0)

    # ------------------------------------------------------------------
    # Improved mapper: inspect both source *and* medium so we can reliably
    # distinguish paid-media clicks (google / cpc, facebook / cpc, etc.).
    # Returns the final Northbeam-style channel name so we do not need an
    # extra alias pass later.
    # ------------------------------------------------------------------

    def _map(src_med: str) -> str:
        """Map a GA4 `Session source / medium` string to a Northbeam channel."""
        val = str(src_med).lower()
        if "/" in val:
            src, med = [p.strip() for p in val.split("/", 1)]
        else:
            src, med = val, ""

        # Paid traffic – identify by medium keywords first
        if med in {"cpc", "ppc", "paid", "paidsocial"}:
            if any(k in src for k in ("google", "g")):
                return "Google Ads"
            if any(k in src for k in ("bing", "microsoft", "msn")):
                return "Microsoft Ads"
            if any(k in src for k in ("facebook", "instagram", "meta")):
                return "Facebook Ads"
            if "tiktok" in src:
                return "TikTok"
            if "pinterest" in src:
                return "Pinterest"
            if any(k in src for k in ("awin", "shopmyshelf", "shareasale", "affiliate")):
                return "Affiliate"

        # --- Organic Search ---
        if med == "organic":
            return "Organic Search"

        # --- Direct / none  -> Unattributed ---
        if src in {"direct", "(not set)", ""} and med in {"(none)", "", "none"}:
            return "Unattributed"

        # Email / SMS specific handling
        if "klaviyo" in src:
            return "Klaviyo"
        if "attentive" in src:
            return "Attentive"
        if med in {"email"} or "email" in src:
            return "Other Email"
        if med in {"sms"} or "sms" in src:
            return "Attentive"
        if "linktree" in src:
            return "LinkTree"
        if "youtube" in src:
            return "YouTube Organic"
        if "reddit" in src:
            return "Reddit"
        if "twitter" in src or "t.co" in src:
            return "Twitter"

        # Organic / referral & catch-all keyword fallback
        for kw, ch in GA_CHANNEL_KEYWORDS.items():
            if kw in src:
                return ch

        return "Other"

    ga_df["channel"] = ga_df["Session source / medium"].apply(_map)
    sess_map = ga_df.groupby("channel")["Sessions"].sum().to_dict()
    return sess_map


# -------------------------------------------------------------
# 🔍  Insights helper (opportunities & challenges)
# -------------------------------------------------------------

def _generate_channel_insights(channel_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (opportunities, challenges) bullet strings from channel performance."""
    opportunities: list[str] = []
    challenges: list[str] = []

    for chan, row in channel_df.iterrows():
        spend = row.get("spend", 0)
        if spend <= 0:
            continue
        roas = row.get("roas", 0)
        cac = row.get("cac", 0)

        # Scale opportunities
        if roas >= 3 and spend >= 10000:
            opportunities.append(
                f"🚀 **Scale Opportunity** – *{chan}* is efficient with **{roas:.2f} ROAS** on **${spend:,.0f}** spend"
            )
        elif roas >= 4 and spend < 10000:
            opportunities.append(
                f"💰 *{chan}* shows excellent **{roas:.2f} ROAS** on limited spend (**${spend:,.0f}**) – consider budget increase"
            )

        # Under-performance flags
        if roas < 1 and spend >= 5000:
            challenges.append(
                f"⚠️ **Under-performing** – *{chan}* delivered low **{roas:.2f} ROAS** on **${spend:,.0f}** spend"
            )
        if cac > 500:
            challenges.append(
                f"💸 High CAC on *{chan}* – **${cac:.0f}**; review targeting & creative"
            )

    return opportunities[:5], challenges[:5]


# -------------------------------------------------------------
# 🏁 Main
# -------------------------------------------------------------

def _aggregate_google_metrics(path: Path | str) -> pd.Series:
    """Return aggregated metrics for Jan–Jun of the CSV year."""
    df = pd.read_csv(path, skiprows=2, thousands=",")
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df = df.dropna(subset=["Day"])
    yr = df["Day"].dt.year.mode()[0]
    h1_df = df[(df["Day"] >= f"{yr}-01-01") & (df["Day"] <= f"{yr}-{H1_MONTH_END}")]

    cols_num = {
        "Cost": "spend",
        "Clicks": "clicks",
        "Impr.": "impr",
        "Conversions": "conv",
        "Conv. value": "rev",
    }
    for src in cols_num:
        h1_df[src] = pd.to_numeric(h1_df[src], errors="coerce").fillna(0)

    spend = h1_df["Cost"].sum()
    clicks = h1_df["Clicks"].sum()
    impr = h1_df["Impr."].sum()
    conv = h1_df["Conversions"].sum()
    rev = h1_df["Conv. value"].sum()

    ctr = clicks / impr * 100 if impr else 0
    avg_cpc = spend / clicks if clicks else 0
    cpa = spend / conv if conv else 0
    roas = rev / spend if spend else 0

    return pd.Series({
        "Spend": spend,
        "Clicks": clicks,
        "Impr": impr,
        "CTR_%": ctr,
        "Avg_CPC": avg_cpc,
        "Conversions": conv,
        "CPA": cpa,
        "ROAS": roas,
        "Revenue": rev,
    })


def _aggregate_meta_metrics(path: Path | str) -> pd.Series:
    df = pd.read_csv(path, thousands=",")
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df = df.dropna(subset=["Day"])
    yr = df["Day"].dt.year.mode()[0]
    h1 = df[(df["Day"] >= f"{yr}-01-01") & (df["Day"] <= f"{yr}-{H1_MONTH_END}")]

    h1_cols = {
        "Amount spent (USD)": "spend",
        "Impressions": "impr",
        "Purchases": "purchases",
        "Purchases conversion value": "rev",
        "CTR (link click-through rate)": "ctr",  # column may vary
        "CTR": "ctr",
    }
    # normalize numeric
    for col in h1_cols:
        if col in h1.columns:
            h1[col] = pd.to_numeric(h1[col], errors="coerce").fillna(0)

    spend = h1["Amount spent (USD)"].sum()
    impr = h1["Impressions"].sum()
    purchases = h1["Purchases"].sum()
    rev = h1["Purchases conversion value"].sum()
    ctr_col = "CTR (link click-through rate)" if "CTR (link click-through rate)" in h1.columns else "CTR"
    ctr_vals = pd.to_numeric(h1.get(ctr_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    ctr = ctr_vals.mean() if not ctr_vals.empty else 0

    cpm = spend / (impr / 1000) if impr else 0
    cpp = spend / purchases if purchases else 0
    roas = rev / spend if spend else 0

    return pd.Series({
        "Spend": spend,
        "Impr": impr,
        "CPM": cpm,
        "CTR_%": ctr,
        "Purchases": purchases,
        "CPP": cpp,
        "ROAS": roas,
        "Revenue": rev,
    })


def main():
    parser = argparse.ArgumentParser(description="Generate H1 growth report")
    parser.add_argument("--northbeam_csv", default=DEFAULT_DIR / "northbeam-2025-ad+platform-date-breakdown-level-ytd-report.csv")
    parser.add_argument("--google_2025_csv", default=DEFAULT_DIR / "google-2025-account-level-ytd-report.csv")
    parser.add_argument("--google_2024_csv", default=DEFAULT_DIR / "google-2024-account-level-ytd-report.csv")
    parser.add_argument("--meta_2025_csv", default=DEFAULT_DIR / "meta-2025-account-level-ytd-report.csv")
    parser.add_argument("--meta_2024_csv", default=DEFAULT_DIR / "meta-2024-account-level-ytd-report.csv")
    parser.add_argument("--ga_2025_csv", default=DEFAULT_DIR / "google-analytics-jan-june-2025-traffic_acquisition_Session_source_medium.csv")
    parser.add_argument("--ga_2024_csv", default=DEFAULT_DIR / "google-analytics-jan-june-2024-traffic_acquisition_Session_source_medium.csv")
    args = parser.parse_args()

    year = 2025  # infer from filename / CLI later

    # Will collect concise YoY bullets here (populated later if 2024 files present)
    yoy_bullets: list[str] = []

    # 1️⃣ Load and filter Northbeam
    nb_df_raw = _load_nb(args.northbeam_csv)
    nb_df = _filter_h1(nb_df_raw, year)

    # 2️⃣ Channel performance with GA sessions & affiliate consolidation

    nb_df_acc = nb_df[nb_df["accounting_mode"] == "Accrual performance"].copy()
    channel_summary = base.analyze_channel_performance(nb_df_acc)

    # Consolidate affiliate-like rows using fuzzy matcher
    affiliate_rows = []
    for idx in channel_summary.index:
        if _is_affiliate_channel(idx):
            affiliate_rows.append(idx)

    if affiliate_rows:
        aff_row = channel_summary.loc[affiliate_rows].sum()
        aff_row.name = "Affiliate"
        channel_summary = channel_summary.drop(index=affiliate_rows)
        if "Affiliate" in channel_summary.index:
            # If Affiliate row already exists (e.g., from data), sum it too.
            aff_row += channel_summary.loc["Affiliate"]
            channel_summary = channel_summary.drop(index=["Affiliate"])
        channel_summary = pd.concat([channel_summary, aff_row.to_frame().T])

    # Load GA sessions and map to channels
    sessions_map_raw = _load_ga_sessions(args.ga_2025_csv)
    sessions_map_2024_raw = _load_ga_sessions(args.ga_2024_csv)

    # Normalize keys so they match Northbeam channel naming
    sessions_map = _apply_alias(sessions_map_raw)
    sessions_2024_map = _apply_alias(sessions_map_2024_raw)

    # Substitute Google Ads sessions with clicks for both 2025 and 2024 so GA tables are realistic
    try:
        g_clicks_25 = _aggregate_google_metrics(args.google_2025_csv)["Clicks"]
        sessions_map["Google Ads"] = g_clicks_25
    except Exception:
        pass

    try:
        g_clicks_24 = _aggregate_google_metrics(args.google_2024_csv)["Clicks"]
        sessions_2024_map["Google Ads"] = g_clicks_24
    except Exception:
        pass

    # -------------------------------------------------------------
    # If we collapsed individual affiliate partners into a single
    # 'Affiliate' channel above, merge their GA session rows too so
    # we do not double-count in the session totals.
    # -------------------------------------------------------------
    if affiliate_rows:
        aff_sess = sum(sessions_map.pop(ch, 0) for ch in affiliate_rows)
        sessions_map["Affiliate"] = sessions_map.get("Affiliate", 0) + aff_sess

    total_spend = channel_summary["spend"].sum()
    total_rev = channel_summary["attributed_rev"].sum()
    total_sessions = sum(sessions_map.values())

    channel_summary["%_spend"] = (channel_summary["spend"] / total_spend * 100).round(1)
    channel_summary["%_rev"] = (channel_summary["attributed_rev"] / total_rev * 100).round(1)
    # Attach GA sessions for reference but compute Conv Rate using Northbeam visits for accuracy
    channel_summary["sessions"] = channel_summary.index.map(lambda x: sessions_map.get(x, 0))

    # -------------------------------------------------------------
    # Google Ads tracking gap: GA & NB both under-count sessions.
    # Substitute Google ad-clicks so CVR is meaningful.
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # 🚦 SESSION HARMONISATION RULES
    #   • Paid-media rows (spend > 0) → use Northbeam visits (tracking loss in GA)
    #   • Retention / owned-media rows (email/SMS) also use NB visits as GA often blocks opens
    #   • All other rows keep GA sessions so organic/referral analysis matches GA.
    # -------------------------------------------------------------

    RETENTION_CHANNELS = {
        "Klaviyo",
        "Attentive",
        "Other Email",
        "Transactional",
        "Yotpo",
    }

    mask_paid = channel_summary["spend"] > 0
    mask_ret = channel_summary.index.isin(RETENTION_CHANNELS)
    harmonise_mask = mask_paid | mask_ret
    channel_summary.loc[harmonise_mask, "sessions"] = channel_summary.loc[harmonise_mask, "visits"]

    # 🡒 Now override Google Ads once more with ad-clicks so visit substitution doesn't overwrite it
    if "Google Ads" in channel_summary.index:
        try:
            g_clicks = _aggregate_google_metrics(args.google_2025_csv)["Clicks"]
            channel_summary.at["Google Ads", "sessions"] = g_clicks
        except Exception:
            pass

    # Use GA sessions (not NB visits) for a more realistic conversion rate
    channel_summary["conv_rate"] = channel_summary.apply(
        lambda r: (r["transactions"] / r["sessions"] if r.get("sessions", 0) else 0),
        axis=1,
    )

    # ---------- Build GA YoY sessions DataFrame ---------- #
    ga_channels = set(sessions_map) | set(sessions_2024_map)
    ga_yoy_rows = []
    for ch in sorted(ga_channels):
        sess25 = sessions_map.get(ch, 0)
        sess24 = sessions_2024_map.get(ch, 0)
        delta = (sess25 - sess24) / sess24 * 100 if sess24 else 0
        ga_yoy_rows.append({"Channel": ch, "Sessions_2025": sess25, "Sessions_2024": sess24, "YoY_%": delta})

    ga_yoy_df = pd.DataFrame(ga_yoy_rows).sort_values("Sessions_2025", ascending=False)

    # Build markdown table for GA YoY
    ga_headers = ["Channel", "2025 Sessions", "2024 Sessions", "YoY Δ%"]
    ga_lines = ["| " + " | ".join(ga_headers) + " |", "|" + "|".join(["-"] * len(ga_headers)) + "|"]
    for _, row in ga_yoy_df.iterrows():
        sign = "+" if row["YoY_%"] > 0 else ("-" if row["YoY_%"] < 0 else "")
        ga_lines.append(
            f"| {row['Channel']} | {int(row['Sessions_2025']):,} | {int(row['Sessions_2024']):,} | {sign}{abs(row['YoY_%']):.0f}% |"
        )

    yoy_ga_md = "\n## 4. Google Analytics – YoY Sessions by Channel\n" + "\n".join(ga_lines) + "\n---\n"

    # Add GA insights bullets (top increases / decreases)
    # Bullet list: top 3 increases and top 3 decreases (negative YoY)
    inc_channels = ga_yoy_df[ga_yoy_df["YoY_%"] > 0].sort_values("YoY_%", ascending=False).head(3)
    dec_channels = ga_yoy_df[ga_yoy_df["YoY_%"] < 0].sort_values("YoY_%").head(3)

    for _, row in inc_channels.iterrows():
        yoy_bullets.append(
            f"* **{row['Channel']} sessions** grew {row['YoY_%']:+.0f}% YoY (GA)"
        )
    for _, row in dec_channels.iterrows():
        yoy_bullets.append(
            f"* **{row['Channel']} sessions** declined {row['YoY_%']:+.0f}% YoY (GA)"
        )

    channel_summary["transactions_display"] = channel_summary["transactions"].round()

    # Build totals row with sessions
    chan_tot = pd.Series({
        "spend": total_spend,
        "attributed_rev": total_rev,
        "roas": total_rev / total_spend if total_spend else 0,
        "cac": total_spend / channel_summary["transactions"].sum() if channel_summary["transactions"].sum() else 0,
        "transactions": channel_summary["transactions"].sum(),
        "transactions_display": channel_summary["transactions"].sum().round(),
        "%_spend": 100.0,
        "%_rev": 100.0,
        "sessions": total_sessions,
        "conv_rate": (channel_summary["transactions"].sum() / total_sessions) if total_sessions else 0,
    }, name="**All Channels**")

    # Sort channels: first those with spend >0 (by spend desc), then zero-spend (by revenue desc)
    paid_ch = channel_summary[channel_summary["spend"] > 0].sort_values(["spend", "attributed_rev"], ascending=[False, False])
    unpaid_ch = channel_summary[channel_summary["spend"] == 0].sort_values("attributed_rev", ascending=False)
    channel_summary_sorted = pd.concat([paid_ch, unpaid_ch])

    channel_display = pd.concat([chan_tot.to_frame().T, channel_summary_sorted]).copy()

    # ---------- NEW: Generate insight bullets ---------- #
    opps, chals = _generate_channel_insights(channel_summary)

    # Build executive-summary specific bullets (scale candidates & under-performers)
    def _build_exec_bullets(df: pd.DataFrame) -> list[str]:
        bullets: list[str] = []
        # Ensure share columns exist
        if "%_spend" not in df.columns:
            return bullets

        # ➊ Scale candidates – high ROAS but <15% of spend
        scale = df[(df["roas"] >= 3) & (df["%_spend"] < 15)].nlargest(3, "spend")
        for idx, r in scale.iterrows():
            bullets.append(
                f"* **Scale {idx}** – ROAS {r.roas:.2f} on only {r['%_spend']:.0f}% of spend"
            )

        # ➋ Under-performers – >5% spend but ROAS <1.0
        under = df[(df["roas"] < 1) & (df["%_spend"] > 5)]
        for idx, r in under.iterrows():
            bullets.append(
                f"* **Reduce {idx}** – ROAS {r.roas:.2f} consuming {r['%_spend']:.0f}% of budget"
            )
        return bullets

    exec_bullets_extra = _build_exec_bullets(channel_summary)

    # Custom markdown table builder with new columns
    def _fmt(val, prefix="", digits=0):
        if prefix:
            return f"{prefix}{val:,.{digits}f}"
        return f"{val:,.{digits}f}" if digits else f"{int(val):,}"

    headers = [
        "Channel", "Spend", "% Spend", "Revenue", "% Rev", "ROAS", "CAC", "Sessions", "Conv Rate", "Transactions",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["-"] * len(headers)) + "|"]

    for idx, row in channel_display.iterrows():
        lines.append(
            "| " + " | ".join([
                str(idx),
                _fmt(row["spend"], "$", 0),
                f"{row['%_spend']:.1f}%",
                _fmt(row["attributed_rev"], "$", 0),
                f"{row['%_rev']:.1f}%",
                f"{row['roas']:.2f}",
                _fmt(row["cac"], "$", 2),
                _fmt(row["sessions"], "", 0),
                f"{row['conv_rate']*100:.2f}%",
                _fmt(row["transactions_display"], "", 0),
            ]) + " |"
        )

    dtc_table_md = f"## 2. DTC Performance – H1 {year} Snapshot (Accrual Performance)\n" + "\n".join(lines) + "\n"

    # ✨ Insight section right after Executive Summary & before tables
    insights_md = ""
    if opps or chals:
        insights_md_lines = ["## 1a. Key Insights", ""]
        if opps:
            insights_md_lines.append("### Opportunities")
            insights_md_lines += [f"* {s}" for s in opps]
        if chals:
            insights_md_lines.append("\n### Challenges")
            insights_md_lines += [f"* {s}" for s in chals]
        insights_md = "\n".join(insights_md_lines) + "\n\n---\n"

    # 3️⃣ Product / Category summaries via cash snapshot rows
    prod_to_cat, alias_sorted, norm_fn = load_product_mappings()
    df_prod = assign_products(nb_df, alias_sorted, norm_fn)
    df_prod["product"] = df_prod["product"].fillna("Unattributed")

    cash_df = df_prod[df_prod["accounting_mode"] == "Cash snapshot"].copy()
    cash_df["category"] = cash_df["product"].map(prod_to_cat).fillna("Unattributed")

    product_summary = build_summary(cash_df, "product")
    category_summary = build_summary(cash_df, "category")

    prod_display = product_summary.copy()
    prod_display["Category"] = prod_display.index.map(prod_to_cat)

    prod_tot = totals_row(prod_display, label="**All Products**")
    prod_tot["Category"] = "—"
    prod_table_df = pd.concat([prod_tot, prod_display])

    cat_tot = totals_row(category_summary, label="**All Categories**")
    category_table_df = pd.concat([cat_tot, category_summary])

    product_section_md = (
        "\n## 2a. Performance by Product (Cash Snapshot)\n" +
        markdown_table(prod_table_df, index_label="Product", extra_col="Category") +
        "\n\n## 2b. Performance by Category (Cash Snapshot)\n" +
        markdown_table(category_table_df, index_label="Category") +
        "\n---\n"
    )

    # 4️⃣ Platform YoY (Google & Meta) – need both years present
    google_25 = _summarize_google(args.google_2025_csv)
    meta_25 = _summarize_meta(args.meta_2025_csv)

    yoy_section_md = ""
    if args.google_2024_csv and args.meta_2024_csv and Path(args.google_2024_csv).exists() and Path(args.meta_2024_csv).exists():
        google_24 = _summarize_google(args.google_2024_csv)
        meta_24 = _summarize_meta(args.meta_2024_csv)

        def _pct(cur, prev):
            return (cur - prev) / prev * 100 if prev else 0

        def _row(cur: dict[str, float], prev: dict[str, float], title: str):
            metrics = [
                ("spend", "$", 0, "Spend"),
                ("rev", "$", 0, "Revenue"),
                ("conv", "", 0, "Conversions"),
                ("roas", "", 2, "ROAS"),
                ("cpa", "$", 2, "CPA"),
            ]
            lines = [f"\n### {title}\n", "| Metric | 2025 | 2024 | YoY Δ% |", "|-|-|-|-|"]
            for key, prefix, d, label in metrics:
                cur_val = cur[key]
                prev_val = prev[key]
                pct = _pct(cur_val, prev_val)
                sign = "+" if pct > 0 else ("-" if pct < 0 else "")
                delta = f"{sign}{abs(pct):.0f}%"
                fmt_cur = f"{prefix}{cur_val:,.{d}f}" if prefix else f"{cur_val:,.{d}f}"
                fmt_prev = f"{prefix}{prev_val:,.{d}f}" if prefix else f"{prev_val:,.{d}f}"
                lines.append(f"| {label} | {fmt_cur} | {fmt_prev} | {delta} |")
            return "\n".join(lines)

        yoy_section_md = (
            "\n## 3. YoY Performance (Jan–Jun)\n" +
            _row(meta_25, meta_24, "Meta Ads") +
            _row(google_25, google_24, "Google Ads") +
            "\n---\n"
        )

        # Prepare concise YoY bullets for later insertion into Executive Summary
        yoy_meta_spend = (meta_25["spend"] - meta_24["spend"]) / meta_24["spend"] * 100 if meta_24["spend"] else 0
        yoy_google_spend = (google_25["spend"] - google_24["spend"]) / google_24["spend"] * 100 if google_24["spend"] else 0
        yoy_bullets.append(
            f"* **Meta Ads**: Spend {yoy_meta_spend:+.0f}% YoY with ROAS {meta_25['roas']:.2f} (was {meta_24['roas']:.2f})"
        )
        yoy_bullets.append(
            f"* **Google Ads**: Spend {yoy_google_spend:+.0f}% YoY with ROAS {google_25['roas']:.2f} (was {google_24['roas']:.2f})"
        )

    # 5️⃣ Executive summary totals (Northbeam Accrual)
    tot_spend = nb_df_acc["spend"].sum()
    tot_rev = nb_df_acc["attributed_rev"].sum()
    tot_txns = nb_df_acc["transactions"].sum()
    roas = tot_rev / tot_spend if tot_spend else 0
    cac = tot_spend / tot_txns if tot_txns else 0

    exec_lines = [
        "## 1. Executive Summary\n",
        f"* **Spend:** ${tot_spend:,.0f}",
        f"* **Revenue:** ${tot_rev:,.0f}",
        f"* **ROAS:** {roas:.2f}",
        f"* **CAC:** ${cac:,.2f}",
    ]

    # Append YoY bullets if we calculated them earlier
    exec_lines.extend(yoy_bullets)
    exec_lines.extend(exec_bullets_extra)

    exec_lines.append("\n")
    exec_md = "\n".join(exec_lines)

    # 6️⃣ Assemble final markdown
    # ---------- NEW SECTIONS --------------------------------------------------

    # Google Ads Efficiency YoY table
    g_metrics_25 = _aggregate_google_metrics(args.google_2025_csv)
    g_metrics_24 = _aggregate_google_metrics(args.google_2024_csv)
    google_eff_df = pd.DataFrame({
        "Metric": g_metrics_25.index,
        "2025": g_metrics_25.values,
        "2024": g_metrics_24.values,
    })
    google_eff_df["YoY_%"] = (google_eff_df["2025"] - google_eff_df["2024"]) / google_eff_df["2024"] * 100

    def _mk_md_table(df: pd.DataFrame, cols: list[str]) -> str:
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["-" for _ in cols]) + "|"]
        for _, r in df.iterrows():
            vals = []
            for c in cols:
                v = r[c]
                if isinstance(v, float):
                    if c in {"2025", "2024"} and r["Metric"] in {"Clicks", "Impr", "Purchases", "Conversions"}:
                        vals.append(f"{int(v):,}")
                    elif c in {"2025", "2024"} and r["Metric"] == "CTR_%":
                        vals.append(f"{v:.2f}%")
                    elif c in {"2025", "2024"} and r["Metric"] in {"Avg_CPC", "CPA", "CPP", "CPM", "Spend", "Revenue"}:
                        vals.append(f"${v:,.2f}")
                    elif c == "YoY_%":
                        sign = "+" if v > 0 else ("-" if v < 0 else "")
                        vals.append(f"{sign}{abs(v):.0f}%")
                    else:
                        vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    google_eff_md = "\n## 5. Google Ads Efficiency – YoY (Jan–Jun)\n" + _mk_md_table(google_eff_df, ["Metric", "2025", "2024", "YoY_%"]) + "\n---\n"

    # Meta Ads Efficiency YoY
    m_metrics_25 = _aggregate_meta_metrics(args.meta_2025_csv)
    m_metrics_24 = _aggregate_meta_metrics(args.meta_2024_csv)
    meta_eff_df = pd.DataFrame({
        "Metric": m_metrics_25.index,
        "2025": m_metrics_25.values,
        "2024": m_metrics_24.values,
    })
    meta_eff_df["YoY_%"] = (meta_eff_df["2025"] - meta_eff_df["2024"]) / meta_eff_df["2024"].replace(0, np.nan) * 100
    meta_eff_md = "\n## 6. Meta Ads Efficiency – YoY (Jan–Jun)\n" + _mk_md_table(meta_eff_df, ["Metric", "2025", "2024", "YoY_%"]) + "\n---\n"

    # Northbeam monthly trend 2025
    nb_month = nb_df_acc.copy()
    nb_month["month"] = nb_month["date"].dt.month_name().str[:3]
    month_sum = nb_month.groupby("month").agg({
        "spend": "sum",
        "attributed_rev": "sum",
        "transactions": "sum",
    })

    # Ensure chronological order (Jan → Dec)
    _month_order = {m: i for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)
    }
    month_sum["_order"] = month_sum.index.map(_month_order)
    month_sum = month_sum.sort_values("_order").drop(columns="_order")

    # Compute performance ratios
    month_sum["ROAS"] = month_sum["attributed_rev"] / month_sum["spend"]
    month_sum["CAC"] = month_sum["spend"] / month_sum["transactions"]

    # Month-over-Month deltas (pct change)
    month_sum["spend_delta"] = month_sum["spend"].pct_change() * 100
    month_sum["rev_delta"] = month_sum["attributed_rev"].pct_change() * 100
    month_sum["txn_delta"] = month_sum["transactions"].pct_change() * 100
    month_sum["cac_delta"] = month_sum["CAC"].pct_change() * 100

    month_sum = month_sum.reset_index()

    # Proper H1 totals (use aggregate values, not sum of ratios)
    h1_spend = month_sum["spend"].sum()
    h1_rev = month_sum["attributed_rev"].sum()
    h1_txn = month_sum["transactions"].sum()
    h1_roas = h1_rev / h1_spend if h1_spend else 0
    h1_cac = h1_spend / h1_txn if h1_txn else 0

    month_sum.loc["Total"] = ["**H1**", h1_spend, h1_rev, h1_txn, h1_roas, h1_cac, None, None, None, None]

    month_md_lines = [
        "| Month | Spend | MoM Δ% | Revenue | MoM Δ% | ROAS | Transactions | MoM Δ% | CAC | MoM Δ% |",
        "| - | - | - | - | - | - | - | - | - | - |",
    ]
    for _, r in month_sum.iterrows():
        spend_delta = "" if pd.isna(r["spend_delta"]) else f"{r['spend_delta']:+.0f}%"
        rev_delta = "" if pd.isna(r["rev_delta"]) else f"{r['rev_delta']:+.0f}%"
        txn_delta = "" if pd.isna(r["txn_delta"]) else f"{r['txn_delta']:+.0f}%"
        cac_delta = "" if pd.isna(r["cac_delta"]) else f"{r['cac_delta']:+.0f}%"
        month_md_lines.append(
            f"| {r['month']} | ${r['spend']:,.0f} | {spend_delta} | ${r['attributed_rev']:,.0f} | {rev_delta} | {r['ROAS']:.2f} | {int(r['transactions']):,} | {txn_delta} | ${r['CAC']:,.2f} | {cac_delta} |"
        )
    month_trend_md = "\n## 7. Monthly Trend – Northbeam (Accrual)\n" + "\n".join(month_md_lines) + "\n---\n"

    # GA Sessions to NB Transactions conversion YoY
    # Use the harmonised session counts from channel_summary when available
    latest_sessions_map = channel_summary["sessions"].to_dict()
    txn_map_25 = nb_df_acc.groupby("breakdown_platform_northbeam")["transactions"].sum().to_dict()

    conv_rows = []
    for ch in ga_channels:  # ga_channels defined earlier
        s25 = latest_sessions_map.get(ch, sessions_map.get(ch, 0))
        s24 = sessions_2024_map.get(ch, 0)
        tx25 = txn_map_25.get(ch, 0)
        conv25 = tx25 / s25 * 100 if s25 else 0
        # conv25 is a percent value; convert to fraction to estimate 2024 txns
        tx24_est = (conv25 / 100) * s24
        conv24_est = (tx24_est / s24 * 100) if s24 else 0
        delta_pp = conv25 - conv24_est
        conv_rows.append({
            "Channel": ch,
            "Sessions_2025": s25,
            "Sessions_2024": s24,
            "YoY_%": (s25 - s24) / s24 * 100 if s24 else 0,
            "Txns_2025": tx25,
            "Txns_2024_est": tx24_est,
            "ConvRate_25": conv25,
            "ConvRate_24_est": conv24_est,
            "Δ_pp": delta_pp,
        })
    conv_df = pd.DataFrame(conv_rows).sort_values("Sessions_2025", ascending=False)
    conv_md_lines = [
        "| Channel | 2025 Sessions | 2024 Sessions | YoY Δ% | 2025 Txns | 2024 Txns (est) | Conv-Rate 25 | Conv-Rate 24 (est) | Δ pp |",
        "| - | - | - | - | - | - | - | - | - |",
    ]
    for _, r in conv_df.iterrows():
        sign = "+" if r["YoY_%"] > 0 else ("-" if r["YoY_%"] < 0 else "")
        conv_md_lines.append(
            f"| {r['Channel']} | {int(r['Sessions_2025']):,} | {int(r['Sessions_2024']):,} | {sign}{abs(r['YoY_%']):.0f}% | {int(r['Txns_2025']):,} | {int(r['Txns_2024_est']):,} | {r['ConvRate_25']:.2f}% | {r['ConvRate_24_est']:.2f}% | {r['Δ_pp']:.2f} |"
        )
    conv_md = (
        "\n## 8. GA Sessions → NB Transactions Conversion\n" +
        "\n".join(conv_md_lines) +
        "\n*2024 transactions and conversion-rate are estimated by applying 2025 channel-level CVR to 2024 sessions (Northbeam not installed in 2024).\nPaid channels use Northbeam visit counts instead of GA sessions, so session totals may differ from Table 4.*\n---\n"
    )

    # Spend / Revenue concentration
    conc_df = channel_summary.copy()
    conc_df = conc_df.sort_values("spend", ascending=False)
    conc_df["spend_share"] = conc_df["spend"] / total_spend * 100
    conc_df["rev_share"] = conc_df["attributed_rev"] / total_rev * 100

    conc_md_lines = ["| Rank | Channel | Spend Share % | Revenue Share % | ROAS |", "| - | - | - | - | - |"]
    for i, (idx, r) in enumerate(conc_df.iterrows(), start=1):
        conc_md_lines.append(
            f"| {i} | {idx} | {r['spend_share']:.0f}% | {r['rev_share']:.0f}% | {r['roas']:.2f} |"
        )
    conc_md = "\n## 9. Spend vs Revenue Concentration (2025)\n" + "\n".join(conc_md_lines[:10]) + "\n---\n"

    # -------------------------------------------------------------
    #  🔮  H2 ACTION PLAN  -----------------------------------------
    # -------------------------------------------------------------

    def _safe_spend(label: str) -> float:
        return channel_summary.loc[label, "spend"] if label in channel_summary.index else 0.0

    fb_spend = _safe_spend("Facebook Ads")
    shift_amt = fb_spend * 0.2  # Example: shift 20% of FB budget

    action_plan = [
        (
            f"1. **Shift ${shift_amt:,.0f} from Facebook Ads to Google PMAX** – maintain blended ROAS ≥ 3.0"
            if fb_spend else "1. **Re-allocate budget toward higher-ROAS channels (Google, Affiliate)**"
        ),
        "2. **Double Microsoft Ads budget** – proven ROAS >6 at low spend",
        "3. **Affiliate optimisation** – renegotiate Awin rev-share, focus on top 5 publishers",
        "4. **Creative testing** – Refresh TikTok & Pinterest hooks (ROAS <0.2)",
        "5. **Ensure Northbeam pixel firing on Meta & TikTok Shops checkout flows",
    ]

    action_md = "\n## 10. H2 Action Plan\n" + "\n".join(action_plan) + "\n"

    # -------------------------------------------------------------------------

    final_md = (
        f"# H1 Growth Report — {year}\n\n" +
        exec_md +
        insights_md +
        dtc_table_md +
        yoy_section_md +
        yoy_ga_md +
        google_eff_md +
        meta_eff_md +
        month_trend_md +
        conv_md +
        conc_md +
        action_md
    )

    # ------------------------------------------------------------------
    # 🗄️  Save report to dedicated output directory (data/reports/h1)
    # ------------------------------------------------------------------
    REPORT_DIR = Path("data/reports/h1")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    out_file = REPORT_DIR / f"h1-growth-report-with-products-{year}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"📝 Markdown report saved to {out_file}")


if __name__ == "__main__":
    main() 