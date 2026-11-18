"""The names of the checks that a story can opt out of with ``checks_ignore``."""

from __future__ import annotations

RULE_NAME = "name"
"""A control that a screen reader announces needs an accessible name."""

RULE_FOCUS = "focus"
"""A control needs to be reachable with the Tab key."""

RULE_CONTRAST = "contrast"
"""Text needs enough contrast against its background."""

CHECK_RULES = (RULE_NAME, RULE_FOCUS, RULE_CONTRAST)
"""Every rule ``checks_ignore`` accepts."""

__all__ = ["CHECK_RULES", "RULE_CONTRAST", "RULE_FOCUS", "RULE_NAME"]
