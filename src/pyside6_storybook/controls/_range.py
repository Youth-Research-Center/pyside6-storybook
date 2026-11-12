"""Validation shared by the controls that take a range."""

from __future__ import annotations


def validate_range(name: str, default: float, minimum: float, maximum: float) -> None:
    """Check that ``minimum <= default <= maximum``.

    Args:
        name: The control's name, used in the error message.
        default: The control's default value.
        minimum: The smallest allowed value.
        maximum: The largest allowed value.

    Raises:
        ValueError: If ``minimum > maximum`` or ``default`` is outside the range.
    """
    if not minimum <= maximum:
        raise ValueError(f"minimum {minimum!r} of control {name!r} is greater than its maximum {maximum!r}")
    if not minimum <= default <= maximum:
        raise ValueError(f"default {default!r} of control {name!r} is outside {minimum!r}..{maximum!r}")
