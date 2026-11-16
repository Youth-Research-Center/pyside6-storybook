"""Argument checks shared by the built-in decorators."""

from __future__ import annotations


def check_int(name: str, value: object) -> int:
    """Return ``value`` if it is an ``int`` (not a ``bool``), otherwise raise ``TypeError`` naming the argument."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {value!r}")
    return value
