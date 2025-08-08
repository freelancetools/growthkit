#!/usr/bin/env python3
"""
File Selection Utility
Interactive file selection from specified directories
"""

import os
import glob
import re
from datetime import datetime
from typing import Optional

from growthkit.utils.style import ansi


def _extract_date_from_filename(filename: str) -> Optional[datetime]:
    """
    Extract the most recent date from various filename patterns.

    Args:
        filename: The filename to parse

    Returns:
        datetime object of the most recent date found, or None if no date found

    Examples:
        "Total sales over time - 2025-01-01 - 2025-08-04.csv" -> 2025-08-04
        "ytd-sales_data-eskiin_llc-2025_08_04_23_29_33_820441.csv" -> 2025-08-04
        "daily-traffic-2025-07-01-2025-08-03-2025.csv" -> 2025-08-03
    """
    basename = os.path.basename(filename)

    # Pattern 1: Date ranges with hyphens (YYYY-MM-DD - YYYY-MM-DD)
    date_range_pattern = r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})'
    date_ranges = re.findall(date_range_pattern, basename)
    if date_ranges:
        # Return the latest end date from all ranges found
        latest_date = None
        for start_date, end_date in date_ranges:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                if latest_date is None or end_dt > latest_date:
                    latest_date = end_dt
            except ValueError:
                continue
        if latest_date:
            return latest_date

    # Pattern 2: Underscored dates (YYYY_MM_DD) - common in timestamped exports
    underscore_pattern = r'(\d{4}_\d{2}_\d{2})'
    underscore_dates = re.findall(underscore_pattern, basename)
    if underscore_dates:
        latest_date = None
        for date_str in underscore_dates:
            try:
                dt = datetime.strptime(date_str, '%Y_%m_%d')
                if latest_date is None or dt > latest_date:
                    latest_date = dt
            except ValueError:
                continue
        if latest_date:
            return latest_date

    # Pattern 3: Single dates with hyphens (YYYY-MM-DD)
    single_date_pattern = r'(\d{4}-\d{2}-\d{2})'
    single_dates = re.findall(single_date_pattern, basename)
    if single_dates:
        latest_date = None
        for date_str in single_dates:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                if latest_date is None or dt > latest_date:
                    latest_date = dt
            except ValueError:
                continue
        if latest_date:
            return latest_date

    return None


def find_latest_by_year(
    base_dir: str,
    recursive_pattern: str,
    year: int | str,
    prefer_daily: bool = True,
) -> str | None:
    """Return the most-recent file matching pattern within ``base_dir`` for a given year.

    Selection rules mirror the executive report's behaviour:
    - Search is recursive using the provided glob ``recursive_pattern`` (e.g., "google-*-daily*.csv").
    - Filter paths that include the given ``year`` string anywhere in the path.
    - Prefer files whose basename contains "daily-" when ``prefer_daily`` is True.
    - Break ties using the most recent parsable date in the filename; fallback to mtime.

    Parameters
    ----------
    base_dir : str
        Root directory to search under (e.g., "data/ads").
    recursive_pattern : str
        Glob pattern (can include "**/") for recursive search.
    year : int | str
        Year to filter for (e.g., 2024).
    prefer_daily : bool, default True
        If True, consider only files whose basename includes "daily-" first.

    Returns
    -------
    str | None
        Path to the selected file or ``None`` when no candidates exist.
    """
    year_str = str(year)
    search_pattern = os.path.join(base_dir, "**", recursive_pattern)
    candidates = [p for p in glob.glob(search_pattern, recursive=True) if year_str in p]

    if not candidates:
        return None

    if prefer_daily:
        daily = [p for p in candidates if "daily-" in os.path.basename(p).lower()]
        pool = daily if daily else candidates
    else:
        pool = candidates

    def _file_sort_key(filepath: str) -> tuple:
        # Primary: most recent date found in filename; Secondary: mtime
        dt = _extract_date_from_filename(filepath)
        if dt is None:
            return (datetime(1970, 1, 1), os.path.getmtime(filepath))
        return (dt, os.path.getmtime(filepath))

    try:
        return max(pool, key=_file_sort_key)
    except ValueError:
        return None


def select_csv_file(
    directory="data/ads",
    file_pattern="*.csv",
    prompt_message=None,
    max_items: int | None = None
):
    """
    Interactive CSV file selection from a directory.

    Args:
        directory: Directory to search for files (default: "stats")
        file_pattern: Glob pattern for file matching (default: "*.csv")
        prompt_message: Custom prompt message (optional)

    Returns:
        str: Selected file path, or None if no selection made
    """
    # Ensure directory exists
    if not os.path.exists(directory):
        print(f"{ansi.red}Error:{ansi.reset} Directory '{directory}' does not exist")
        return None

    # Find all matching files
    search_pattern = os.path.join(directory, file_pattern)
    files = glob.glob(search_pattern)

    if not files:
        print(f"{ansi.yellow}No files found{ansi.reset} matching pattern '{file_pattern}' in '{directory}'")
        return None

    # Sort files by filename date first, then by modification time (newest first)
    def _file_sort_key(filepath: str) -> tuple:
        """Sort key: (-extracted_date_timestamp, -modification_time)"""
        extracted_date = _extract_date_from_filename(filepath)
        if extracted_date:
            # Use negative timestamp for reverse chronological order
            date_score = -extracted_date.timestamp()
        else:
            # Use minimum date score to sort files without dates last
            date_score = -datetime(1970, 1, 1).timestamp()

        mod_time_score = -os.path.getmtime(filepath)
        return (date_score, mod_time_score)

    files.sort(key=_file_sort_key)

    # Limit to most recent N files if requested
    if max_items is not None:
        files = files[:max_items]

    # Display options
    print(f"\n{ansi.cyan}Available files in {directory}:{ansi.reset}")
    print("-" * 50)

    for i, file_path in enumerate(files, 1):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)

        # Get date info - prefer extracted date over modification time
        extracted_date = _extract_date_from_filename(file_path)
        if extracted_date:
            date_info = f"Data: {extracted_date.strftime('%Y-%m-%d')}"
        else:
            mtime = os.path.getmtime(file_path)
            mod_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            date_info = f"Modified: {mod_date}"

        print(f"{ansi.green}{i:2}.{ansi.reset} {filename}")
        print(f"     {ansi.grey}Size: {size_mb:.1f} MB | {date_info}{ansi.reset}")

    # Get user selection
    if prompt_message:
        prompt = prompt_message
    else:
        prompt = f"\n{ansi.yellow}Select a file{ansi.reset} (1-{len(files)}, or 'q' to quit): "

    while True:
        try:
            choice = input(prompt).strip().lower()

            if choice == 'q' or choice == 'quit':
                print(f"{ansi.yellow}Selection cancelled{ansi.reset}")
                return None

            file_index = int(choice) - 1

            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                filename = os.path.basename(selected_file)
                print(f"\n{ansi.green}Selected:{ansi.reset} {filename}")
                return selected_file
            else:
                print(f"{ansi.red}Invalid selection.{ansi.reset} Please choose 1-{len(files)} or 'q' to quit.")

        except ValueError:
            print(f"{ansi.red}Invalid input.{ansi.reset} Please enter a number 1-{len(files)} or 'q' to quit.")
        except KeyboardInterrupt:
            print(f"\n{ansi.yellow}Selection cancelled{ansi.reset}")
            return None


def select_data_file_for_report(report_type="weekly"):
    """
    Specialized function for selecting data files for reports.

    Args:
        report_type: "weekly" or "monthly" to filter appropriate files

    Returns:
        str: Selected file path, or None if no selection made
    """
    if report_type.lower() == "weekly":
        pattern = "*7d*sales_data*.csv"
        message = f"\n{ansi.cyan}Select 7-day sales data file for weekly report:{ansi.reset} "
    elif report_type.lower() == "monthly":
        pattern = "*30D*sales_data*.csv"
        message = f"\n{ansi.cyan}Select 30-day sales data file for monthly report:{ansi.reset} "
    else:
        pattern = "*sales_data*.csv"
        message = f"\n{ansi.cyan}Select sales data file for {report_type} report:{ansi.reset} "

    return select_csv_file(
        directory="data/ads",
        file_pattern=pattern,
        prompt_message=message
    )


if __name__ == "__main__":
    # Test the file selection
    print("Testing file selection utility...")
    selected = select_csv_file()
    if selected:
        print(f"You selected: {selected}")
    else:
        print("No file selected")