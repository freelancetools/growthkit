"""
Tests for platform column mapping in weekly.load_and_clean_data().

When 'breakdown_platform_northbeam' is missing, the loader should:
- Map from 'platform' if present
- Else map from 'channel' if present
- Else map from 'breakdown_platform' if present
- Else create placeholder column with value 'Unknown'
"""

from pathlib import Path

import pandas as pd

from growthkit.reports import weekly


def _write_csv(tmp_dir: Path, df: pd.DataFrame, name: str) -> str:
    """Helper function to write a DataFrame to CSV and return the path."""
    path = tmp_dir / name
    df.to_csv(path, index=False)
    return str(path)


def test_maps_from_platform_when_missing_required_col(tmp_path, monkeypatch):
    """Test that 'platform' column is mapped to when the required column is missing."""
    df = pd.DataFrame({
        "platform": ["Google Ads", "Meta Ads"],
        "spend": [100, 200],
    })
    csv_path = _write_csv(tmp_path, df, "platform_source.csv")
    monkeypatch.setattr(weekly, "select_csv_file", lambda **kwargs: csv_path)

    cleaned = weekly.load_and_clean_data()
    assert cleaned is not None
    assert "breakdown_platform_northbeam" in cleaned.columns
    assert list(cleaned["breakdown_platform_northbeam"]) == ["Google Ads", "Meta Ads"]


def test_maps_from_channel_when_platform_absent(tmp_path, monkeypatch):
    """Test that 'channel' column is mapped when 'platform' is not available."""
    df = pd.DataFrame({
        "channel": ["TikTok Ads", "Pinterest Ads"],
        "spend": [50, 60],
    })
    csv_path = _write_csv(tmp_path, df, "channel_source.csv")
    monkeypatch.setattr(weekly, "select_csv_file", lambda **kwargs: csv_path)

    cleaned = weekly.load_and_clean_data()
    assert cleaned is not None
    assert "breakdown_platform_northbeam" in cleaned.columns
    assert list(cleaned["breakdown_platform_northbeam"]) == ["TikTok Ads", "Pinterest Ads"]


def test_inserts_unknown_when_no_alternatives(tmp_path, monkeypatch):
    """Test that 'Unknown' placeholder is used when no alternative columns are available."""
    df = pd.DataFrame({
        "spend": [1, 2, 3],
        "attributed_rev": [0, 0, 0],
    })
    csv_path = _write_csv(tmp_path, df, "no_alternatives.csv")
    monkeypatch.setattr(weekly, "select_csv_file", lambda **kwargs: csv_path)

    cleaned = weekly.load_and_clean_data()
    assert cleaned is not None
    assert "breakdown_platform_northbeam" in cleaned.columns
    assert set(cleaned["breakdown_platform_northbeam"]) == {"Unknown"}
