"""``TextControl``: a single-line text argument."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextControl:
    """A single-line text argument.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value.
    """

    name: str
    default: str


__all__ = ["TextControl"]
