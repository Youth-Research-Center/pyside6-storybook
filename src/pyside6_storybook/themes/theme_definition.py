"""``ThemeDefinition``: the name, colour scheme and palette colours of one built-in theme."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette


@dataclass(frozen=True, slots=True)
class ThemeDefinition:
    """One built-in theme.

    Attributes:
        name: The name shown in the theme switch.
        color_scheme: The colour scheme requested from Qt for platform-drawn parts (title bars, native dialogs).
        colors: Colour of each palette role, used for every colour group. Stored as a read-only copy.
        disabled_colors: Colours that override ``colors`` in the Disabled group. Stored as a read-only copy.
    """

    name: str
    color_scheme: Qt.ColorScheme
    colors: Mapping[QPalette.ColorRole, str]
    disabled_colors: Mapping[QPalette.ColorRole, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "colors", MappingProxyType(dict(self.colors)))
        object.__setattr__(self, "disabled_colors", MappingProxyType(dict(self.disabled_colors)))

    def palette(self) -> QPalette:
        """Build the theme's palette: ``colors`` in every colour group, then ``disabled_colors`` in the Disabled group."""
        palette = QPalette()
        for role, color in self.colors.items():
            palette.setColor(role, QColor(color))
        for role, color in self.disabled_colors.items():
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(color))
        return palette


__all__ = ["ThemeDefinition"]
