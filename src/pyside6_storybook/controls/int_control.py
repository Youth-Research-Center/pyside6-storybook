"""``IntControl``: an integer argument within an inclusive range."""

from __future__ import annotations

from dataclasses import dataclass

from pyside6_storybook.controls._range import validate_range

_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


@dataclass(frozen=True, slots=True)
class IntControl:
    """An integer argument within an inclusive range.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must lie within the range.
        minimum: Smallest allowed value.
        maximum: Largest allowed value.

    Raises:
        ValueError: If a bound is outside the signed 32-bit range the editor (``QSpinBox``) supports, ``minimum > maximum`` or
            ``default`` is outside the range.
    """

    name: str
    default: int
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if self.minimum < _INT32_MIN or self.maximum > _INT32_MAX:
            raise ValueError(f"bounds of control {self.name!r} must fit in a signed 32-bit integer ({_INT32_MIN}..{_INT32_MAX})")
        validate_range(self.name, self.default, self.minimum, self.maximum)


__all__ = ["IntControl"]
