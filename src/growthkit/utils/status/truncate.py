#!/usr/bin/env python3
"""
Utility script to reduce the size of large git-diff files by truncating the body
of diff hunks for files matching certain extensions (e.g. *.har).  For every
matching diff section, the script keeps the first *N* and last *N* lines (N is
configurable, default 10) and replaces the omitted middle part with a concise
summary line such as:

    ... [truncated 1 234 lines] ...

All other diff sections (non-matching files) are copied verbatim, so the overall
structure of the diff remains intact.

Example
-------
$ python truncate.py session.diff session_trunc.diff --ext .har --lines 10

If *output* is omitted and *--inplace* is **not** given, the truncated diff is
printed to stdout.  With *--inplace* the input file is overwritten.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import deque
from typing import Iterable, List
from dataclasses import dataclass

DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/\1(?:\s|$)")


def iter_lines(fp) -> Iterable[str]:
    """Iterate over *fp* yielding decoded text lines.

    Accepts *fp* as filename, pathlib.Path, or a file-like object.
    """
    if isinstance(fp, (str, os.PathLike)):
        # Auto-detect encoding via BOM because PowerShell's redirection (> file)
        # writes UTF-16 LE by default.  Fallback to UTF-8 if no BOM found.
        path = os.fspath(fp)
        with open(path, "rb") as probe:
            prefix = probe.read(4)

        if prefix.startswith(b"\xff\xfe"):
            enc = "utf-16-le"
        elif prefix.startswith(b"\xfe\xff"):
            enc = "utf-16-be"
        elif prefix.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"  # UTF-8 with BOM
        else:
            enc = "utf-8"

        with open(path, "r", encoding=enc, errors="replace") as f:
            for line in f:
                yield line
    else:  # assume file-like
        for line in fp:
            yield line


@dataclass
class DiffSection:
    """In-memory representation of a diff section."""

    header: List[str]
    first: List[str]
    last: deque[str]
    truncated_count: int
    is_target: bool

    def flush(self, fp_out) -> None:
        """Write the section to *fp_out* applying truncation if *is_target*."""
        if not self.header:
            return  # nothing to do (e.g. at start of file)

        if self.is_target and self.truncated_count > 0:
            # Truncate body.
            fp_out.writelines(self.header)
            fp_out.writelines(self.first)
            fp_out.write(f"... [truncated {self.truncated_count} lines] ...\n")
            fp_out.writelines(self.last)
        else:
            # Either not a target or diff small enough – write entire section.
            fp_out.writelines(self.header)
            fp_out.writelines(self.first)
            fp_out.writelines(self.last)



def truncate_diff(
    src: Iterable[str],
    dst,  # file-like object opened for text writing
    *,
    exts: list[str] | tuple[str, ...] = (".har",),
    keep: int = 10,
) -> None:
    """Read git *src* diff, write truncated version to *dst*.

    Parameters
    ----------
    src
        Iterable of diff lines (usually from a file).
    dst
        Writeable text file-like object.
    exts
        Sequence of file extensions (with leading dot) to truncate.
    keep
        Number of lines to preserve at both the beginning and end of matching
        sections.
    """
    exts_set = {e.lower() for e in exts}

    section = DiffSection(
        header=[], first=[],
        last=deque(maxlen=keep),
        truncated_count=0, is_target=False
    )
    line_iter = iter(src)

    for line in line_iter:
        if line.startswith("diff --git"):
            # New diff header encountered – flush current section first.
            section.flush(dst)

            # Start a new section.
            section = DiffSection(
                header=[line], first=[],
                last=deque(maxlen=keep), truncated_count=0,
                is_target=False
                )

            # Examine the filename to decide whether to truncate.
            m = DIFF_HEADER_RE.match(line)
            if m:
                filepath = m.group(1)
                _, ext = os.path.splitext(filepath)
                section.is_target = ext.lower() in exts_set
        else:
            # Body line.
            if not section.is_target:
                # Non-target – store everything in header to output verbatim.
                section.header.append(line)
            else:
                # Target – apply truncation logic.
                if len(section.first) < keep:
                    section.first.append(line)
                else:
                    # Past the first *keep* lines – maintain ring buffer of *last*.
                    if len(section.last) == section.last.maxlen:
                        section.truncated_count += 1  # dropping a line from last
                    section.last.append(line)

    # Flush the final section.
    section.flush(dst)



def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # noqa: ANN401
    p = argparse.ArgumentParser(description="Truncate large diff sections for specific file extensions.")
    p.add_argument("input", help="Path to the original git diff file or '-' for stdin")
    p.add_argument("output", nargs="?", help="Path for the truncated diff (default: stdout)")
    p.add_argument("--ext", "-e", action="append", default=[".har"], dest="exts", help="File extension(s) to target, e.g. -e .har -e .zip (default: .har)")
    p.add_argument("--lines", "-n", type=int, default=10, help="Number of lines to keep at start and end (default: 10)")
    p.add_argument("--inplace", "-i", action="store_true", help="Overwrite the input file in-place instead of writing to OUTPUT")
    return p.parse_args(argv)



def main(argv: list[str] | None = None) -> None:
    """
    python truncate_diff.py session.diff session_trunc.diff --ext .har --lines 10
    """
    ns = _parse_args(argv)

    input_fp = sys.stdin if ns.input == "-" else ns.input
    output_path = (
        ns.input if ns.inplace else ns.output or "-"
    )  # if inplace, write back to same file

    if output_path == "-":
        output_fp = sys.stdout
    else:
        output_fp = open(output_path, "w", encoding="utf-8")

    try:
        truncate_diff(iter_lines(input_fp), output_fp, exts=ns.exts, keep=ns.lines)
    finally:
        if output_fp is not sys.stdout:
            output_fp.close()


if __name__ == "__main__":
    main()
