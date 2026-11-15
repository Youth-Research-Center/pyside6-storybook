"""``TextControl``: a text argument."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyside6_storybook.controls._options import derive_label, validate_flag, validate_label_and_description


@dataclass(frozen=True, slots=True)
class TextControl:
    """A text argument.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.
        multiline: Edit the text in a multi-line editor instead of a single-line one.

    Raises:
        TypeError: If ``default`` is not a string, ``label`` or ``description`` has the wrong type, or ``multiline`` is not a bool.
        ValueError: If ``label`` is blank.
    """

    name: str
    default: str
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)
    multiline: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        validate_flag(self.name, "multiline", self.multiline)
        self.coerce(self.default)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> str:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            ``value``, which must be a string.

        Raises:
            TypeError: If ``value`` is not a string.
        """
        if not isinstance(value, str):
            raise TypeError(f"value {value!r} of control {self.name!r} must be a string")
        return value


__all__ = ["TextControl"]
