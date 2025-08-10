"""
Tests for growthkit.utils.status.truncate.truncate_diff

Covers:
- Truncation for target extensions with correct summary line and kept edges
- Pass-through for non-target extensions
- No truncation when section length <= 2 * keep
- Handling multiple diff sections in one input
"""

from io import StringIO
from typing import Iterable, List

from growthkit.utils.status.truncate import truncate_diff


def _make_diff_section(filename: str, body_lines: int) -> List[str]:
    """Create a simple git diff section for a single file with N body lines.

    The header format is crafted to match DIFF_HEADER_RE so the section is recognized.
    """
    header = [f"diff --git a/{filename} b/{filename}\n"]
    # Minimal body; in real diffs there would be index/---/+++/@@, but
    # the truncation logic treats everything after the header as body lines.
    body = [f"line {i}\n" for i in range(1, body_lines + 1)]
    return header + body


def _run_truncate(src_lines: Iterable[str], *, exts, keep: int) -> str:
    out = StringIO()
    truncate_diff(src_lines, out, exts=exts, keep=keep)
    return out.getvalue()


def test_truncate_on_target_extension_inserts_summary_and_keeps_edges():
    keep = 2
    src = _make_diff_section("trace.har", body_lines=8)
    result = _run_truncate(src, exts=[".har"], keep=keep)

    # Expect: header + first 2 + summary + last 2
    expected_prefix = (
        "diff --git a/trace.har b/trace.har\n"
        "line 1\n"
        "line 2\n"
    )
    assert result.startswith(expected_prefix)

    # Summary line should reflect dropped middle lines: 8 - 2 - 2 = 4
    assert "... [truncated 4 lines] ...\n" in result

    # Verify last lines are preserved and in order
    assert result.rstrip().endswith("line 7\nline 8")


def test_non_target_extension_is_unchanged():
    keep = 2
    src = _make_diff_section("module.py", body_lines=6)
    original = "".join(src)
    result = _run_truncate(src, exts=[".har"], keep=keep)
    assert result == original


def test_small_target_section_not_truncated_when_within_limit():
    keep = 2
    # 2 * keep equals 4; ensure body length equals 4 → no truncation
    src = _make_diff_section("small.har", body_lines=4)
    original = "".join(src)
    result = _run_truncate(src, exts=[".har"], keep=keep)
    assert result == original


def test_multiple_sections_mixed_target_and_non_target():
    keep = 2
    section1 = _make_diff_section("a.har", body_lines=7)  # should truncate (7 > 4)
    section2 = _make_diff_section("b.txt", body_lines=3)  # non-target, unchanged
    combined = section1 + section2

    result = _run_truncate(combined, exts=[".har"], keep=keep)

    # First section has summary
    assert "diff --git a/a.har b/a.har\n" in result
    assert "... [truncated 3 lines] ...\n" in result  # 7 - 2 - 2 = 3
    assert "line 1\n" in result and "line 2\n" in result
    assert "line 6\n" in result and "line 7\n" in result

    # Second section is verbatim
    second_original = "".join(section2)
    assert second_original in result
