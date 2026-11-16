"""``FloatControl``: a floating-point argument within an inclusive range."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pyside6_storybook.controls._options import (
    MAX_FLOAT_DECIMALS,
    derive_label,
    fits_decimals,
    float_step_and_decimals,
    is_number,
    validate_flag,
    validate_label_and_description,
)
from pyside6_storybook.controls._range import validate_range

MAX_SLIDER_STEPS = 10_000
"""The most steps a float slider may have: ``(maximum - minimum) / step`` rounded up."""


@dataclass(frozen=True, slots=True)
class FloatControl:
    """A floating-point argument within an inclusive range.

    The editor shows ``effective_decimals`` decimals, so ``coerce`` rejects a value that would be rounded by it, and so does the
    constructor for the default and the bounds. A default or bound that needs more than 10 decimals is therefore rejected.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must lie within the range.
        minimum: Smallest allowed value.
        maximum: Largest allowed value.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.
        step: The editor's single step, ``> 0`` and at most the range; ``None`` derives a power of ten near 1% of the range.
            A zero-width range (``minimum == maximum``) uses ``1.0`` and does not accept an explicit step.
        decimals: Decimals the editor shows, ``0..10``; ``None`` derives the fewest (at least 2) that represent the step, the
            default and both bounds exactly.
        slider: Show a slider beside the spin box. Its positions are ``0..slider_steps``; position ``i`` means
            ``min(minimum + i * effective_step, maximum)``, and the last position is always exactly ``maximum``.

    Raises:
        TypeError: If a value is not a number, ``decimals`` is not an integer, ``slider`` is not a bool, or ``label`` or
            ``description`` has the wrong type.
        ValueError: If a value is not finite, ``minimum > maximum``, ``default`` is outside the range, ``step`` or ``decimals`` is
            out of its range, ``decimals`` is too small for the step, the default or a bound, a value needs more than 10
            decimals, a slider would have more than 10 000 steps, or ``label`` is blank.
    """

    name: str
    default: float
    minimum: float
    maximum: float
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)
    step: float | None = field(default=None, kw_only=True)
    decimals: int | None = field(default=None, kw_only=True)
    slider: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        validate_flag(self.name, "slider", self.slider)
        for field_name in ("default", "minimum", "maximum"):
            value = getattr(self, field_name)
            if not is_number(value):
                raise TypeError(f"{field_name} of control {self.name!r} must be a number, not {value!r}")
        if not all(math.isfinite(value) for value in (self.default, self.minimum, self.maximum)):
            raise ValueError(f"default, minimum and maximum of control {self.name!r} must be finite")
        validate_range(self.name, self.default, self.minimum, self.maximum)
        self._validate_step()
        self._validate_decimals()
        self.coerce(self.default)
        if self.slider and self.slider_steps > MAX_SLIDER_STEPS:
            raise ValueError(
                f"the slider of control {self.name!r} would have {self.slider_steps} steps, more than {MAX_SLIDER_STEPS}; use a larger step"
            )

    def _validate_step(self) -> None:
        if self.step is None:
            return
        if not is_number(self.step):
            raise TypeError(f"step of control {self.name!r} must be a number, not {self.step!r}")
        if self.minimum == self.maximum:
            raise ValueError(f"control {self.name!r} has a zero-width range, so it does not accept a step")
        if not 0 < self.step <= self.maximum - self.minimum:
            span = self.maximum - self.minimum
            raise ValueError(f"step {self.step!r} of control {self.name!r} must be greater than 0 and at most the range {span!r}")

    def _validate_decimals(self) -> None:
        if self.decimals is not None:
            if not isinstance(self.decimals, int) or isinstance(self.decimals, bool):
                raise TypeError(f"decimals of control {self.name!r} must be an integer, not {self.decimals!r}")
            if not 0 <= self.decimals <= MAX_FLOAT_DECIMALS:
                raise ValueError(f"decimals {self.decimals!r} of control {self.name!r} must be between 0 and {MAX_FLOAT_DECIMALS}")
        decimals = self.effective_decimals
        values = {"step": self.effective_step, "default": self.default, "minimum": self.minimum, "maximum": self.maximum}
        for what, value in values.items():
            if not fits_decimals(value, decimals):
                advice = "raise decimals=" if self.decimals is not None else "it needs more decimals than an editor can show"
                raise ValueError(f"the {what} {value!r} of control {self.name!r} cannot be shown with {decimals} decimals: {advice}")

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    @property
    def effective_step(self) -> float:
        """The editor's single step: ``step``, or a power of ten near 1% of the range (``1.0`` for a zero-width range)."""
        return float_step_and_decimals(
            default=self.default, minimum=self.minimum, maximum=self.maximum, step=self.step, decimals=self.decimals
        )[0]

    @property
    def effective_decimals(self) -> int:
        """The decimals the editor shows: ``decimals``, or the fewest (at least 2, at most 10) that represent the step, the default
        and both bounds exactly."""
        return float_step_and_decimals(
            default=self.default, minimum=self.minimum, maximum=self.maximum, step=self.step, decimals=self.decimals
        )[1]

    @property
    def slider_steps(self) -> int:
        """The number of steps of the slider, which has positions ``0..slider_steps``: ``ceil((maximum - minimum) / step - 1e-9)``."""
        return max(0, math.ceil((self.maximum - self.minimum) / self.effective_step - 1e-9))

    def coerce(self, value: object) -> float:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            ``value`` as a ``float``. It must be an ``int`` or ``float`` (not a ``bool``), finite, within the range, and not
            changed by rounding to ``effective_decimals`` decimals, which is what the editor would do to it.

        Raises:
            TypeError: If ``value`` is not an ``int`` or ``float``.
            ValueError: If ``value`` is too large for a float, is not finite, is outside the range, or needs more decimals than the
                editor shows.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"value {value!r} of control {self.name!r} must be a number")
        try:
            number = float(value)
        except OverflowError:
            raise ValueError(f"value {value!r} of control {self.name!r} is too large for a float") from None
        if not math.isfinite(number):
            raise ValueError(f"value {value!r} of control {self.name!r} must be finite")
        if not self.minimum <= number <= self.maximum:
            raise ValueError(f"value {value!r} of control {self.name!r} is outside {self.minimum!r}..{self.maximum!r}")
        decimals = self.effective_decimals
        if not fits_decimals(number, decimals):
            raise ValueError(f"value {value!r} of control {self.name!r} needs more than {decimals} decimals; set decimals= to show more")
        return number


__all__ = ["MAX_SLIDER_STEPS", "FloatControl"]
