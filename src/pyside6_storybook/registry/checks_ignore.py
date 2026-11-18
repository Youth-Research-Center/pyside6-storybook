"""``coerce_checks_ignore``: the check opt-outs of a story, validated and read-only."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pyside6_storybook.checks.rules import CHECK_RULES

NO_CHECKS_IGNORED: Mapping[str, str] = MappingProxyType({})
"""The empty opt-out, the default of ``checks_ignore``."""


def coerce_checks_ignore(story_id: str, value: Mapping[str, str]) -> Mapping[str, str]:
    """Return ``value`` as a read-only copy after checking its rules and reasons.

    Args:
        story_id: The story's id, for the error messages.
        value: Check rule names mapped to the reason the story opts out of them.

    Returns:
        A read-only mapping with its own copy of the items.

    Raises:
        TypeError: If ``value`` is not a mapping.
        ValueError: If a rule is not one of ``CHECK_RULES`` or a reason is not a non-blank string.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"Story {story_id!r}: checks_ignore must map rule names to reasons, not {value!r}")
    for rule, reason in value.items():
        if rule not in CHECK_RULES:
            raise ValueError(f"Story {story_id!r}: unknown rule {rule!r} in checks_ignore; expected one of {', '.join(map(repr, CHECK_RULES))}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"Story {story_id!r}: checks_ignore[{rule!r}] needs a reason, a non-blank string saying why the rule does not apply")
    return MappingProxyType(dict(value))


__all__ = ["NO_CHECKS_IGNORED", "coerce_checks_ignore"]
