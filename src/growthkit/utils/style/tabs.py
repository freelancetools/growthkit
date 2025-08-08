"""Regex pattern to match lines that are only tabs, we remove these in the main script."""
TABREGEX = r"""
^[\t ]+$
"""
