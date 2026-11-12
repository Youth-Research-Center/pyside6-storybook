"""The built-in Light theme."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from pyside6_storybook.themes.theme_definition import ThemeDefinition

_ROLE = QPalette.ColorRole

LIGHT_THEME = ThemeDefinition(
    name="Light",
    color_scheme=Qt.ColorScheme.Light,
    colors={
        _ROLE.Window: "#F0F0F0",
        _ROLE.WindowText: "#1B1B1B",
        _ROLE.Base: "#FFFFFF",
        _ROLE.AlternateBase: "#F5F5F5",
        _ROLE.ToolTipBase: "#FFFFE1",
        _ROLE.ToolTipText: "#1B1B1B",
        _ROLE.PlaceholderText: "#6B6B6B",
        _ROLE.Text: "#1B1B1B",
        _ROLE.Button: "#E6E6E6",
        _ROLE.ButtonText: "#1B1B1B",
        _ROLE.BrightText: "#FFFFFF",
        _ROLE.Light: "#FFFFFF",
        _ROLE.Midlight: "#EDEDED",
        _ROLE.Dark: "#A0A0A0",
        _ROLE.Mid: "#B8B8B8",
        _ROLE.Shadow: "#000000",
        _ROLE.Highlight: "#2A6FDB",
        _ROLE.HighlightedText: "#FFFFFF",
        _ROLE.Link: "#0B57D0",
        _ROLE.LinkVisited: "#6B3FA0",
        _ROLE.Accent: "#2A6FDB",
    },
    disabled_colors={
        _ROLE.WindowText: "#8A8A8A",
        _ROLE.Text: "#8A8A8A",
        _ROLE.ButtonText: "#8A8A8A",
        _ROLE.PlaceholderText: "#A8A8A8",
        _ROLE.BrightText: "#E0E0E0",
        _ROLE.Highlight: "#B0B0B0",
        _ROLE.HighlightedText: "#F0F0F0",
        _ROLE.Accent: "#B0B0B0",
    },
)


def light_palette() -> QPalette:
    """Return the built-in light palette."""
    return LIGHT_THEME.palette()


__all__ = ["LIGHT_THEME", "light_palette"]
