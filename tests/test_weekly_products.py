"""
Tests for product mapping and summary helpers in growthkit.reports.weekly
"""

import pandas as pd

from growthkit.reports.weekly import (
    load_product_mappings,
    detect_product,
    assign_products,
    build_summary,
    markdown_table,
    totals_row,
)


def test_detect_product_uses_aliases_and_multiple_fields():
    """Test that the detect_product function uses aliases and multiple fields."""
    product_to_category, alias_sorted, norm_fn = load_product_mappings()

    # Alias appears in ad_name
    row1 = {
        "ad_name": "PEMF Mat Spring Sale",
        "adset_name": "",
        "campaign_name": "",
    }
    prod1 = detect_product(row1, alias_sorted, norm_fn)
    assert prod1 in product_to_category  # canonical product detected

    # Alias appears only in campaign_name
    row2 = {
        "ad_name": "",
        "adset_name": "",
        "campaign_name": "Red Light Mask Promo",
    }
    prod2 = detect_product(row2, alias_sorted, norm_fn)
    assert prod2 in product_to_category
    assert prod1 != prod2  # different canonical products


def test_assign_products_build_summary_and_markdown_prev_delta():
    """Test that the assign_products, build_summary, and markdown_table functions work."""
    _product_to_category, alias_sorted, norm_fn = load_product_mappings()

    # Two products; second has zero spend to ensure safe division handling
    df = pd.DataFrame(
        [
            {
                "ad_name": "pemf mat",
                "adset_name": "",
                "campaign_name": "",
                "spend": 100.0,
                "attributed_rev": 300.0,
                "attributed_rev_1st_time": 150.0,
                "transactions": 10.0,
                "transactions_1st_time": 5.0,
            },
            {
                "ad_name": "red light mask",
                "adset_name": "",
                "campaign_name": "",
                "spend": 0.0,
                "attributed_rev": 200.0,
                "attributed_rev_1st_time": 50.0,
                "transactions": 4.0,
                "transactions_1st_time": 2.0,
            },
        ]
    )

    df_prod = assign_products(df, alias_sorted, norm_fn)
    assert "product" in df_prod.columns
    assert df_prod["product"].notna().all()

    summary = build_summary(df_prod, "product")
    # Basic metric sanity checks
    assert {"roas", "cac", "aov", "transactions_display"}.issubset(summary.columns)

    # The PEMF product should have ROAS 3.0 (300/100) and CAC = 100/10 = 10
    pemf_row = summary.loc[summary.index.str.contains("PEMF", case=False)].iloc[0]
    assert abs(pemf_row["roas"] - 3.0) < 1e-6
    assert abs(pemf_row["cac"] - 10.0) < 1e-6

    # Build a previous summary with lower numbers to test Δ% formatting
    prev_df = df.copy()
    prev_df["spend"] = prev_df["spend"] * 0.5
    prev_df["attributed_rev"] = prev_df["attributed_rev"] * 0.5
    prev_df["attributed_rev_1st_time"] = prev_df["attributed_rev_1st_time"] * 0.5
    prev_df["transactions"] = prev_df["transactions"] * 0.5
    prev_df["transactions_1st_time"] = prev_df["transactions_1st_time"] * 0.5
    prev_prod = assign_products(prev_df, alias_sorted, norm_fn)
    prev_summary = build_summary(prev_prod, "product")

    md = markdown_table(summary, index_label="Product", prev_summary=prev_summary)
    # Expect delta columns, with positive percentages due to current > previous
    assert "%" in md
    assert "Product" in md

    # Include a totals row and ensure it aligns with summary aggregates
    tot = totals_row(summary, label="**All Products**")
    assert float(tot["spend"].iloc[0]) == float(summary["spend"].sum())
    assert float(tot["attributed_rev"].iloc[0]) == float(summary["attributed_rev"].sum())
