"""Regression harness: runs every golden question from data/golden_questions.md
against the live API and reports pass/fail for each.

Usage:
    uv run python scripts/test_golden.py --base-url http://localhost:8000

Exit code 0 if all questions pass, 1 if any fail.
"""
