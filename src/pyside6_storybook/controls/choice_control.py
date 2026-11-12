"""``ChoiceControl``: an argument that is one of a fixed list of strings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChoiceControl:
    """An argument that is one of a fixed list of strings.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must be one of ``options``.
        options: The allowed values. Any sequence of strings is accepted; it is stored as a tuple.

    Raises:
        TypeError: If ``options`` is a bare string instead of a sequence of strings.
        ValueError: If ``default`` is not one of ``options``.
    """

    name: str
    default: str
    options: Sequence[str]

    def __post_init__(self) -> None:
        if isinstance(self.options, str):
            raise TypeError(f"options of control {self.name!r} must be a sequence of strings, not a single string")
        options = tuple(self.options)
        object.__setattr__(self, "options", options)
        if self.default not in options:
            raise ValueError(f"default {self.default!r} of control {self.name!r} is not one of its options {options!r}")


__all__ = ["ChoiceControl"]
