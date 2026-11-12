"""Control definitions: the editable arguments of a story."""

from __future__ import annotations

import math
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


@dataclass(frozen=True, slots=True)
class BoolControl:
    """A boolean argument.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value.
    """

    name: str
    default: bool


@dataclass(frozen=True, slots=True)
class ChoiceControl:
    """An argument that is one of a fixed list of strings.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must be one of ``options``.
        options: The allowed values. Any sequence of strings is accepted and stored as a tuple.

    Raises:
        TypeError: If ``options`` is a bare string instead of a sequence of strings.
        ValueError: If ``default`` is not one of ``options``.
    """

    name: str
    default: str
    options: tuple[str, ...]

    def __post_init__(self) -> None:
        if isinstance(self.options, str):
            raise TypeError(f"options of control {self.name!r} must be a sequence of strings, not a single string")
        options = tuple(self.options)
        object.__setattr__(self, "options", options)
        if self.default not in options:
            raise ValueError(f"default {self.default!r} of control {self.name!r} is not one of its options {options!r}")


@dataclass(frozen=True, slots=True)
class IntControl:
    """An integer argument within an inclusive range.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must lie within the range.
        minimum: Smallest allowed value.
        maximum: Largest allowed value.

    Raises:
        ValueError: If ``minimum > maximum`` or ``default`` is outside the range.
    """

    name: str
    default: int
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        _validate_range(self.name, self.default, self.minimum, self.maximum)


@dataclass(frozen=True, slots=True)
class FloatControl:
    """A floating-point argument within an inclusive range.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must lie within the range.
        minimum: Smallest allowed value.
        maximum: Largest allowed value.

    Raises:
        ValueError: If a value is not finite, ``minimum > maximum`` or ``default`` is outside the range.
    """

    name: str
    default: float
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.default, self.minimum, self.maximum)):
            raise ValueError(f"default, minimum and maximum of control {self.name!r} must be finite")
        _validate_range(self.name, self.default, self.minimum, self.maximum)


Control = TextControl | BoolControl | ChoiceControl | IntControl | FloatControl
"""Any control type."""


def _validate_range(name: str, default: float, minimum: float, maximum: float) -> None:
    if not minimum <= maximum:
        raise ValueError(f"minimum {minimum!r} of control {name!r} is greater than its maximum {maximum!r}")
    if not minimum <= default <= maximum:
        raise ValueError(f"default {default!r} of control {name!r} is outside {minimum!r}..{maximum!r}")


__all__ = [
    "BoolControl",
    "ChoiceControl",
    "Control",
    "FloatControl",
    "IntControl",
    "TextControl",
]
