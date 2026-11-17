"""The application's theme manager: two themes, Paper (light) and Ink (dark), each a style sheet, a palette and design tokens."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from string import Template

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

_STYLE_SHEET = Template(
    """
QPushButton#pillButton {
    background: $accent;
    color: $on_accent;
    border: none;
    border-radius: 14px;
    padding: 6px 18px;
}
QPushButton#pillButton:hover { background: $accent_hover; }
QPushButton#pillButton:disabled { background: $track; color: $muted; }
"""
)

_ROLE = QPalette.ColorRole


@dataclass(frozen=True, slots=True)
class Theme:
    """One theme: its colours as ``#rrggbb`` strings, from which the style sheet, the palette and the tokens are built."""

    name: str
    window: str
    base: str
    text: str
    muted: str
    button: str
    accent: str
    accent_hover: str
    on_accent: str
    track: str

    def tokens(self) -> dict[str, str]:
        """Return the design tokens a custom-painted widget reads."""
        return {"accent": self.accent, "surface": self.window, "text": self.text, "track": self.track, "on_accent": self.on_accent}

    def style_sheet(self) -> str:
        """Return the application style sheet."""
        return _STYLE_SHEET.substitute(asdict(self))

    def palette(self) -> QPalette:
        """Return a complete palette for the theme, with a muted colour for the Disabled group."""
        palette = QPalette()
        colors = {
            _ROLE.Window: self.window,
            _ROLE.WindowText: self.text,
            _ROLE.Base: self.base,
            _ROLE.AlternateBase: self.button,
            _ROLE.Text: self.text,
            _ROLE.Button: self.button,
            _ROLE.ButtonText: self.text,
            _ROLE.BrightText: self.on_accent,
            _ROLE.ToolTipBase: self.base,
            _ROLE.ToolTipText: self.text,
            _ROLE.PlaceholderText: self.muted,
            _ROLE.Highlight: self.accent,
            _ROLE.HighlightedText: self.on_accent,
            _ROLE.Accent: self.accent,
            _ROLE.Link: self.accent,
            _ROLE.LinkVisited: self.accent,
            _ROLE.Light: self.base,
            _ROLE.Midlight: self.button,
            _ROLE.Mid: self.track,
            _ROLE.Dark: self.track,
            _ROLE.Shadow: self.track,
        }
        for role, color in colors.items():
            palette.setColor(role, QColor(color))
        for role in (_ROLE.WindowText, _ROLE.Text, _ROLE.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(self.muted))
        return palette


THEMES = {
    theme.name: theme
    for theme in (
        Theme(
            "Paper",
            window="#f6f1e7",
            base="#fffdf8",
            text="#2b2622",
            muted="#6b6258",
            button="#e9dfcc",
            accent="#9a4a12",
            accent_hover="#7d3a0a",
            on_accent="#ffffff",
            track="#d9cdb4",
        ),
        Theme(
            "Ink",
            window="#14181f",
            base="#1c222b",
            text="#e6e9ee",
            muted="#9aa4b2",
            button="#2a3342",
            accent="#7ab8ff",
            accent_hover="#9fcdff",
            on_accent="#0b0e12",
            track="#37414f",
        ),
    )
}
_FONT_POINT_SIZE = 11


class ThemeManager(QObject):
    """Holds the application's themes and applies one to a ``QApplication``; ``themeChanged`` fires after every change."""

    themeChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current = next(iter(THEMES))

    def names(self) -> tuple[str, ...]:
        """Return the theme names."""
        return tuple(THEMES)

    def current(self) -> str:
        """Return the name of the current theme."""
        return self._current

    def tokens(self) -> Mapping[str, str]:
        """Return the design tokens of the current theme."""
        return THEMES[self._current].tokens()

    def apply(self, app: QApplication, name: str) -> None:
        """Apply a theme: its palette, style sheet and font. Emits ``themeChanged``.

        Args:
            app: The application to style.
            name: One of ``names()``.

        Raises:
            ValueError: If ``name`` is not one of ``names()``.
        """
        if name not in THEMES:
            raise ValueError(f"Unknown theme {name!r}; expected one of {self.names()}")
        theme = THEMES[name]
        self._current = name
        # Polish every widget first: Qt can crash when the application style sheet changes while a widget exists that was never polished
        # (see the library's AGENTS.md, "Qt hygiene").
        for widget in QApplication.allWidgets():
            widget.ensurePolished()
        app.setPalette(theme.palette())
        app.setStyleSheet(theme.style_sheet())
        font = QFont(app.font())
        font.setPointSize(_FONT_POINT_SIZE)
        app.setFont(font)
        self.themeChanged.emit()
