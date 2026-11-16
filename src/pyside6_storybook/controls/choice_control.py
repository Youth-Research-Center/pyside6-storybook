"""``ChoiceControl``: an argument that is one of a fixed list of strings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from pyside6_storybook.controls._options import derive_label, validate_label_and_description


@dataclass(frozen=True, slots=True)
class ChoiceControl:
    """An argument that is one of a fixed list of strings.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; must be one of ``options``.
        options: The allowed values. Any sequence of strings is accepted; it is stored as a tuple.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.

    Raises:
        TypeError: If ``options`` is a bare string instead of a sequence of strings, ``default`` is not a string, or ``label`` or
            ``description`` has the wrong type.
        ValueError: If ``default`` is not one of ``options``, or ``label`` is blank.
    """

    name: str
    default: str
    options: Sequence[str]
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)

    def __post_init__(self) -> None:
        if isinstance(self.options, str):
            raise TypeError(f"options of control {self.name!r} must be a sequence of strings, not a single string")
        object.__setattr__(self, "options", tuple(self.options))
        validate_label_and_description(self.name, self.label, self.description)
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
            ``value``, which must be one of ``options``.

        Raises:
            TypeError: If ``value`` is not a string.
            ValueError: If ``value`` is not one of ``options``.
        """
        if not isinstance(value, str):
            raise TypeError(f"value {value!r} of control {self.name!r} must be a string")
        if value not in self.options:
            raise ValueError(f"value {value!r} of control {self.name!r} is not one of its options {tuple(self.options)!r}")
        return value


__all__ = ["ChoiceControl"]
