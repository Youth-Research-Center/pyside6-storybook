"""Checks that a hand-written test can run on any widget; the pytest plugin runs them on every story with ``--storybook-a11y``.

``check_accessible_names``, ``check_keyboard_focus`` and ``check_text_contrast`` return a ``CheckIssue`` for each problem, so an
empty list means the widget passes.
"""

from __future__ import annotations

from pyside6_storybook.checks.accessibility import check_accessible_names, check_keyboard_focus
from pyside6_storybook.checks.check_issue import CheckIssue
from pyside6_storybook.checks.contrast import check_text_contrast

__all__ = ["CheckIssue", "check_accessible_names", "check_keyboard_focus", "check_text_contrast"]
