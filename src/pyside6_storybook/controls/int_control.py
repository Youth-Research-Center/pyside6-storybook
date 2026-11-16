"""``IntControl``: an integer argument within an inclusive range."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyside6_storybook.controls._options import derive_label, validate_flag, validate_label_and_description
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
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.
        step: The editor's single step (arrow keys, and the slider's keys); at least 1.
        slider: Show a slider beside the spin box.

    Raises:
        TypeError: If ``default``, a bound or ``step`` is not an integer, ``slider`` is not a bool, or ``label`` or ``description``
            has the wrong type.
        ValueError: If a bound is outside the signed 32-bit range the editor (``QSpinBox``) supports, ``minimum > maximum``,
            ``default`` is outside the range, ``step`` is below 1, or ``label`` is blank.
    """

    name: str
    default: int
    minimum: int
    maximum: int
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)
    step: int = field(default=1, kw_only=True)
    slider: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        validate_flag(self.name, "slider", self.slider)
        for field_name in ("default", "minimum", "maximum", "step"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} of control {self.name!r} must be an integer, not {value!r}")
        if self.minimum < _INT32_MIN or self.maximum > _INT32_MAX:
            raise ValueError(f"bounds of control {self.name!r} must fit in a signed 32-bit integer ({_INT32_MIN}..{_INT32_MAX})")
        if self.step < 1:
            raise ValueError(f"step {self.step!r} of control {self.name!r} must be at least 1")
        validate_range(self.name, self.default, self.minimum, self.maximum)
        self.coerce(self.default)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> int:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            ``value``, which must be an ``int`` within the range.

        Raises:
            TypeError: If ``value`` is not an ``int``; a ``bool`` is not accepted.
            ValueError: If ``value`` is outside the range.
        """
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"value {value!r} of control {self.name!r} must be an integer")
        if not self.minimum <= value <= self.maximum:
            raise ValueError(f"value {value!r} of control {self.name!r} is outside {self.minimum!r}..{self.maximum!r}")
        return value


__all__ = ["IntControl"]
