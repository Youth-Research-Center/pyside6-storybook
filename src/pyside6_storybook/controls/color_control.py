"""``ColorControl``: a colour argument."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PySide6.QtGui import QColor

from pyside6_storybook.controls._options import derive_label, validate_flag, validate_label_and_description

_HEX_COLOR = re.compile(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})?")
_OPAQUE = 255


@dataclass(frozen=True, slots=True)
class ColorControl:
    """A colour argument. The story receives a ``QColor``; the default is a hex string.

    The accepted strings are, in either case, exactly ``#RRGGBB`` and, with ``alpha=True``, ``#RRGGBBAA`` (the CSS byte order, with
    the alpha byte last). Colour names and the short ``#RGB`` form are not accepted.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value, a hex string.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.
        alpha: Allow a translucent colour: the editor's dialog shows an alpha channel and ``#RRGGBBAA`` is accepted.

    Raises:
        TypeError: If ``default`` is not a string, ``alpha`` is not a bool, or ``label`` or ``description`` has the wrong type.
        ValueError: If ``default`` is not a valid hex colour for this control, or ``label`` is blank.
    """

    name: str
    default: str
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)
    alpha: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        validate_flag(self.name, "alpha", self.alpha)
        if not isinstance(self.default, str):
            raise TypeError(f"default of control {self.name!r} must be a hex colour string such as '#336699', not {self.default!r}")
        self.coerce(self.default)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> QColor:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value: a hex string or a ``QColor``.

        Returns:
            A new ``QColor`` on every call.

        Raises:
            TypeError: If ``value`` is neither a string nor a ``QColor``.
            ValueError: If a string is not a hex colour in this control's grammar, or a ``QColor`` is invalid or translucent without
                ``alpha=True``.
        """
        if isinstance(value, QColor):
            if not value.isValid():
                raise ValueError(f"value of control {self.name!r} is an invalid QColor")
            if value.alpha() != _OPAQUE and not self.alpha:
                hex_argb = value.name(QColor.NameFormat.HexArgb)
                raise ValueError(f"value {hex_argb!r} of control {self.name!r} is translucent; set alpha=True to allow it")
            return QColor(value)
        if not isinstance(value, str):
            raise TypeError(f"value {value!r} of control {self.name!r} must be a hex colour string or a QColor")
        match = _HEX_COLOR.fullmatch(value)
        if match is None:
            expected = "'#RRGGBB' or '#RRGGBBAA'" if self.alpha else "'#RRGGBB'"
            raise ValueError(f"value {value!r} of control {self.name!r} is not a hex colour like {expected}")
        red, green, blue, alpha = match.groups()
        if alpha is not None and not self.alpha:
            raise ValueError(f"value {value!r} of control {self.name!r} has an alpha byte; set alpha=True to allow it")
        return QColor(int(red, 16), int(green, 16), int(blue, 16), _OPAQUE if alpha is None else int(alpha, 16))


__all__ = ["ColorControl"]
