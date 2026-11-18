"""Checks that a hand-written test can run on any widget; the pytest plugin runs them on every story with ``--storybook-a11y``.

``check_accessible_names`` and ``check_keyboard_focus`` return a ``CheckIssue`` for each problem, so an empty list means the widget passes.
"""

from __future__ import annotations

from pyside6_storybook.checks.accessibility import check_accessible_names, check_keyboard_focus
from pyside6_storybook.checks.check_issue import CheckIssue

__all__ = ["CheckIssue", "check_accessible_names", "check_keyboard_focus"]
