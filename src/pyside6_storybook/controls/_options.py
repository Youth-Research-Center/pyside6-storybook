"""Functions shared by the controls: label derivation, option validation and the float step and decimals rules."""

from __future__ import annotations

import math

MIN_FLOAT_DECIMALS = 2
"""The fewest decimals a float editor derives when ``decimals`` is not given."""
MAX_FLOAT_DECIMALS = 10
"""The most decimals a float editor can show, derived or explicit."""

_FLOAT_STEPS_PER_RANGE = 100
_FLOAT_NOISE = 1e-15
"""Relative difference treated as floating-point noise (a few units in the last place), not as a change of value."""


def derive_label(name: str) -> str:
    """Return the form label derived from an argument name, for example ``"tile_type"`` becomes ``"Tile Type"``.

    Args:
        name: The control's name.

    Returns:
        The name with underscores replaced by spaces and each word capitalised.
    """
    return name.replace("_", " ").title()


def validate_label_and_description(name: str, label: object, description: object) -> None:
    """Check the ``label`` and ``description`` fields every control has.

    Args:
        name: The control's name, used in the error message.
        label: The declared label: ``None`` or a non-blank string.
        description: The declared description: a string.

    Raises:
        TypeError: If ``label`` is neither ``None`` nor a string, or ``description`` is not a string.
        ValueError: If ``label`` is blank.
    """
    if label is not None:
        if not isinstance(label, str):
            raise TypeError(f"label of control {name!r} must be a string or None, not {label!r}")
        if not label.strip():
            raise ValueError(f"label of control {name!r} must not be blank; use None to derive it from the name")
    if not isinstance(description, str):
        raise TypeError(f"description of control {name!r} must be a string, not {description!r}")


def validate_flag(name: str, field_name: str, value: object) -> None:
    """Check that a boolean option such as ``slider`` or ``multiline`` is a ``bool``.

    Args:
        name: The control's name, used in the error message.
        field_name: The option's name.
        value: The declared value.

    Raises:
        TypeError: If ``value`` is not a ``bool``.
    """
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} of control {name!r} must be True or False, not {value!r}")


def is_number(value: object) -> bool:
    """Return whether ``value`` is an ``int`` or ``float``, and not a ``bool``."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fits_decimals(value: float, decimals: int) -> bool:
    """Return whether ``value`` survives rounding to ``decimals`` decimals, which is what a ``QDoubleSpinBox`` does to it.

    Only floating-point noise is tolerated (``0.1 * 3`` fits one decimal); any real change, however small or at whatever magnitude
    (``1e-16`` or ``1000000000.0001`` with two decimals), does not fit.
    """
    return math.isclose(round(value, decimals), value, rel_tol=_FLOAT_NOISE, abs_tol=0.0)


def decimals_needed(value: float) -> int:
    """Return the fewest decimals (up to ``MAX_FLOAT_DECIMALS``) that represent ``value`` without changing it."""
    for decimals in range(MAX_FLOAT_DECIMALS + 1):
        if fits_decimals(value, decimals):
            return decimals
    return MAX_FLOAT_DECIMALS


def float_step_and_decimals(
    *, default: float, minimum: float, maximum: float, step: float | None, decimals: int | None
) -> tuple[float, int]:
    """Return a float editor's spin box step and decimals.

    Without an explicit ``step`` the step is a power of ten near 1% of the range (``1.0`` for a zero-width range). Without explicit
    ``decimals`` the decimals are the fewest, at least ``MIN_FLOAT_DECIMALS`` and at most ``MAX_FLOAT_DECIMALS``, that represent the
    step, the default and both bounds exactly, so the editor shows the exact default and cannot round a bound.

    Args:
        default: The control's default.
        minimum: The smallest allowed value.
        maximum: The largest allowed value.
        step: The explicit step, or ``None`` to derive it.
        decimals: The explicit decimals, or ``None`` to derive them.

    Returns:
        The step and the decimals.
    """
    if step is None:
        span = maximum - minimum
        step = 1.0 if span <= 0 else 10.0 ** round(math.log10(span / _FLOAT_STEPS_PER_RANGE))
    if decimals is None:
        decimals = max(MIN_FLOAT_DECIMALS, *(decimals_needed(value) for value in (step, default, minimum, maximum)))
    return step, decimals
