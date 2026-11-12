"""The built-in Dark theme."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from pyside6_storybook.themes.theme_definition import ThemeDefinition

_ROLE = QPalette.ColorRole

DARK_THEME = ThemeDefinition(
    name="Dark",
    color_scheme=Qt.ColorScheme.Dark,
    colors={
        _ROLE.Window: "#2B2B2B",
        _ROLE.WindowText: "#E6E6E6",
        _ROLE.Base: "#1E1E1E",
        _ROLE.AlternateBase: "#262626",
        _ROLE.ToolTipBase: "#3A3A3A",
        _ROLE.ToolTipText: "#E6E6E6",
        _ROLE.PlaceholderText: "#A0A0A0",
        _ROLE.Text: "#E6E6E6",
        _ROLE.Button: "#3A3A3A",
        _ROLE.ButtonText: "#E6E6E6",
        _ROLE.BrightText: "#FFFFFF",
        _ROLE.Light: "#6A6A6A",
        _ROLE.Midlight: "#505050",
        _ROLE.Dark: "#151515",
        _ROLE.Mid: "#4A4A4A",
        _ROLE.Shadow: "#000000",
        _ROLE.Highlight: "#2F6FD0",
        _ROLE.HighlightedText: "#FFFFFF",
        _ROLE.Link: "#6CA6FF",
        _ROLE.LinkVisited: "#B08CFF",
        _ROLE.Accent: "#2F6FD0",
    },
    disabled_colors={
        _ROLE.WindowText: "#7A7A7A",
        _ROLE.Text: "#7A7A7A",
        _ROLE.ButtonText: "#7A7A7A",
        _ROLE.PlaceholderText: "#6A6A6A",
        _ROLE.BrightText: "#9A9A9A",
        _ROLE.Highlight: "#555555",
        _ROLE.HighlightedText: "#9A9A9A",
        _ROLE.Accent: "#555555",
    },
)


def dark_palette() -> QPalette:
    """Return the built-in dark palette."""
    return DARK_THEME.palette()


__all__ = ["DARK_THEME", "dark_palette"]
