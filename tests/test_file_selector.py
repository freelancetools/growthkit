"""
Tests for growthkit.reports.file_selector
"""
import os
import time
from pathlib import Path

from growthkit.reports import file_selector as fs


def test_find_latest_by_year_respects_filename_dates_across_patterns(tmp_path: Path):
    """
    Test that the file selector respects filename dates across different patterns.
    """
    # Create files with different date encodings; ensure mtime would otherwise mislead
    f_range = tmp_path / "Total sales over time - 2025-01-01 - 2025-08-04.csv"
    f_underscore = tmp_path / "ytd-sales_data-eskiin_llc-2025_08_04_23_29_33_820441.csv"
    f_multi = tmp_path / "daily-traffic-2025-07-01-2025-08-03-2025.csv"

    for p in (f_range, f_underscore, f_multi):
        p.write_text("x")

    now = time.time()
    # Set mtimes to intentionally conflict with the true latest-by-filename-date
    # Latest-by-date should be 2025-08-04 (f_range and f_underscore), choose by mtime secondary
    os.utime(f_range, (now - 30, now - 30))       # older mtime
    os.utime(f_underscore, (now - 10, now - 10))  # newest mtime among latest-date set
    os.utime(f_multi, (now - 5, now - 5))         # newest mtime overall but older date (2025-08-03)

    selected = fs.find_latest_by_year(str(tmp_path), "*.csv", 2025, prefer_daily=False)
    assert selected is not None
    # Should prefer the most recent filename date (Aug 4) and then by mtime among equals
    assert Path(selected).name == f_underscore.name or Path(selected).name == f_range.name
    # Specifically, since both have 2025 in name and same date, mtime tie-breaker picks f_underscore
    assert Path(selected).name == f_underscore.name


def test_find_latest_by_year_prefers_daily_and_latest_within_daily(tmp_path: Path):
    """
    Test that the file selector prefers daily files and selects the latest within daily.
    """
    base = tmp_path
    (base / "a").mkdir()
    f1 = base / "a" / "google-2025-daily-2025-08-03.csv"
    f2 = base / "a" / "google-2025-daily-2025-08-04.csv"
    f3 = base / "a" / "google-2025-export-2025-08-05.csv"
    for p in (f1, f2, f3):
        p.write_text("x")

    now = time.time()
    os.utime(f1, (now - 30, now - 30))
    os.utime(f2, (now - 20, now - 20))
    os.utime(f3, (now - 10, now - 10))

    selected = fs.find_latest_by_year(str(base), "*.csv", 2025, prefer_daily=True)
    assert selected is not None
    assert Path(selected).name == "google-2025-daily-2025-08-04.csv"


def test_find_latest_by_year_fallback_to_mtime_without_date(tmp_path: Path):
    """
    Test that the file selector falls back to mtime when no date pattern is found.
    """
    base = tmp_path
    (base / "dir").mkdir()
    f1 = base / "dir" / "report-2025.csv"  # contains year marker but no date pattern
    f2 = base / "dir" / "another-2025.csv"
    f1.write_text("x")
    f2.write_text("x")

    now = time.time()
    os.utime(f1, (now - 50, now - 50))
    os.utime(f2, (now - 10, now - 10))

    selected = fs.find_latest_by_year(str(base), "*.csv", "2025", prefer_daily=False)
    assert selected is not None
    assert Path(selected).name == "another-2025.csv"


def test_find_latest_by_year_filters_by_year(tmp_path: Path):
    """
    Test that the file selector filters by year.
    """
    base = tmp_path
    (base / "x").mkdir()
    f2024 = base / "x" / "google-2024-daily-2024-08-04.csv"
    f2025 = base / "x" / "google-2025-daily-2025-08-04.csv"
    f2024.write_text("x")
    f2025.write_text("x")

    sel_2024 = fs.find_latest_by_year(str(base), "*.csv", 2024, prefer_daily=True)
    sel_2025 = fs.find_latest_by_year(str(base), "*.csv", 2025, prefer_daily=True)

    assert sel_2024 is not None and "2024" in Path(sel_2024).name
    assert sel_2025 is not None and "2025" in Path(sel_2025).name
