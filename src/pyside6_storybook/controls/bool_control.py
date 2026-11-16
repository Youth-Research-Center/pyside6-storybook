"""``BoolControl``: a boolean argument."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyside6_storybook.controls._options import derive_label, validate_label_and_description


@dataclass(frozen=True, slots=True)
class BoolControl:
    """A boolean argument.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.

    Raises:
        TypeError: If ``default`` is not a bool, or ``label`` or ``description`` has the wrong type.
        ValueError: If ``label`` is blank.
    """

    name: str
    default: bool
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        self.coerce(self.default)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> bool:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            ``value``, which must be a ``bool``; ``0`` and ``1`` are not accepted.

        Raises:
            TypeError: If ``value`` is not a ``bool``.
        """
        if not isinstance(value, bool):
            raise TypeError(f"value {value!r} of control {self.name!r} must be True or False")
        return value


__all__ = ["BoolControl"]
