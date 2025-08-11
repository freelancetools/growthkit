"""
Tests for promotion of alternative revenue sources in weekly.load_and_clean_data.

This covers the logic that promotes web/meta_shops/tiktok_shops revenue and
transactions into attributed_rev/transactions when attributed_rev is zero, and
falls back to 'rev' when available. Also asserts the diagnostic flags are set.
"""

from pathlib import Path
import pandas as pd
from growthkit.reports import weekly


def _write_csv(tmp_dir: Path) -> str:
    """Create a minimal CSV exercising each promotion path and return its path."""
    rows = [
        # row_id, accounting_mode, attributed_rev, attributed_rev_1st_time, transactions, transactions_1st_time,
        # web_revenue, web_transactions, meta_shops_revenue, meta_shops_transactions,
        # tiktok_shops_revenue, tiktok_shops_transactions, rev, breakdown_platform_northbeam
        [
            "web",
            "Accrual performance",
            0,
            0,
            0,
            0,
            100,
            2,
            0,
            0,
            0,
            0,
            0,
            "Google Ads",
        ],
        [
            "meta",
            "Accrual performance",
            0,
            0,
            0,
            0,
            0,
            0,
            50,
            1,
            0,
            0,
            0,
            "Meta Ads",
        ],
        [
            "tiktok",
            "Accrual performance",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            40,
            3,
            0,
            "TikTok Ads",
        ],
        [
            "rev",
            "Accrual performance",
            0,
            0,
            4,  # pre-existing transactions should remain unchanged for 'rev' fallback
            2,
            0,
            0,
            0,
            0,
            0,
            0,
            75,
            "Other",
        ],
    ]

    df = pd.DataFrame(
        rows,
        columns=[
            "row_id",
            "accounting_mode",
            "attributed_rev",
            "attributed_rev_1st_time",
            "transactions",
            "transactions_1st_time",
            "web_revenue",
            "web_transactions",
            "meta_shops_revenue",
            "meta_shops_transactions",
            "tiktok_shops_revenue",
            "tiktok_shops_transactions",
            "rev",
            "breakdown_platform_northbeam",
        ],
    )

    csv_path = tmp_dir / "weekly_promotions_fixture.csv"
    df.to_csv(csv_path, index=False)
    return str(csv_path)


def test_load_and_clean_data_promotes_alt_sources(tmp_path, monkeypatch):
    """Promotion of web/meta_shops/tiktok_shops and rev fallback should work."""
    csv_path = _write_csv(tmp_path)

    # Force the loader to use our synthetic CSV instead of interactive prompt
    monkeypatch.setattr(weekly, "select_csv_file", lambda **kwargs: csv_path)

    df = weekly.load_and_clean_data()
    assert df is not None

    # Helper to select a single row by id
    def row(rid: str) -> pd.Series:
        sel = df.loc[df["row_id"] == rid]
        assert not sel.empty, f"Missing row_id={rid} in cleaned DataFrame"
        return sel.iloc[0]

    r_web = row("web")
    assert r_web["attributed_rev"] == 100
    assert r_web["transactions"] == 2
    assert r_web.get("attributed_rev_1st_time", 0) == 100
    assert r_web.get("transactions_1st_time", 0) == 2
    assert bool(r_web.get("used_web_metrics", False)) is True

    r_meta = row("meta")
    assert r_meta["attributed_rev"] == 50
    assert r_meta["transactions"] == 1
    assert r_meta.get("attributed_rev_1st_time", 0) == 50
    assert r_meta.get("transactions_1st_time", 0) == 1
    assert bool(r_meta.get("used_meta_shops_metrics", False)) is True

    r_tt = row("tiktok")
    assert r_tt["attributed_rev"] == 40
    assert r_tt["transactions"] == 3
    assert r_tt.get("attributed_rev_1st_time", 0) == 40
    assert r_tt.get("transactions_1st_time", 0) == 3
    assert bool(r_tt.get("used_tiktok_shops_metrics", False)) is True

    r_rev = row("rev")
    # Only attributed_rev should be promoted from 'rev'; transactions unchanged
    assert r_rev["attributed_rev"] == 75
    assert r_rev["transactions"] == 4
    # No first-time promotion for 'rev' fallback path
    assert r_rev.get("attributed_rev_1st_time", 0) == 0
    assert r_rev.get("transactions_1st_time", 0) == 2
    assert bool(r_rev.get("used_rev_metrics", False)) is True
