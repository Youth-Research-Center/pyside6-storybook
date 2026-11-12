"""``BoolControl``: a boolean argument."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoolControl:
    """A boolean argument.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value.
    """

    name: str
    default: bool


__all__ = ["BoolControl"]
