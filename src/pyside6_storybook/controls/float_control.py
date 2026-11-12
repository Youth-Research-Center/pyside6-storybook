"""``FloatControl``: a floating-point argument within an inclusive range."""

from __future__ import annotations

import math
from dataclasses import dataclass

from pyside6_storybook.controls._range import validate_range


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
        validate_range(self.name, self.default, self.minimum, self.maximum)


__all__ = ["FloatControl"]
