"""Built-in Light and Dark themes: the Fusion style plus an explicit palette.

Qt's own colour-scheme switch (``QStyleHints.setColorScheme``) does nothing on the offscreen platform and its effect depends
on the platform style, so it cannot be the basis of a theme. Each built-in theme instead sets the Fusion style and a complete
``QPalette``, which looks the same on every platform. ``setColorScheme`` is still called on a best-effort basis so that
parts drawn by the platform (title bars, native dialogs) follow the theme where Qt supports it.

An application-wide style sheet takes precedence over the palette for the widgets it styles, so the built-in themes have no
visible effect on those widgets while such a style sheet is set.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_ROLE = QPalette.ColorRole

_LIGHT: Mapping[QPalette.ColorRole, str] = {
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
}

_LIGHT_DISABLED: Mapping[QPalette.ColorRole, str] = {
    _ROLE.WindowText: "#8A8A8A",
    _ROLE.Text: "#8A8A8A",
    _ROLE.ButtonText: "#8A8A8A",
    _ROLE.PlaceholderText: "#A8A8A8",
    _ROLE.BrightText: "#E0E0E0",
    _ROLE.Highlight: "#B0B0B0",
    _ROLE.HighlightedText: "#F0F0F0",
    _ROLE.Accent: "#B0B0B0",
}

_DARK: Mapping[QPalette.ColorRole, str] = {
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
}

_DARK_DISABLED: Mapping[QPalette.ColorRole, str] = {
    _ROLE.WindowText: "#7A7A7A",
    _ROLE.Text: "#7A7A7A",
    _ROLE.ButtonText: "#7A7A7A",
    _ROLE.PlaceholderText: "#6A6A6A",
    _ROLE.BrightText: "#9A9A9A",
    _ROLE.Highlight: "#555555",
    _ROLE.HighlightedText: "#9A9A9A",
    _ROLE.Accent: "#555555",
}


def _build_palette(active: Mapping[QPalette.ColorRole, str], disabled: Mapping[QPalette.ColorRole, str]) -> QPalette:
    """Build a palette that sets ``active`` for every colour group and then overrides ``disabled`` in the Disabled group."""
    palette = QPalette()
    for role, color in active.items():
        palette.setColor(role, QColor(color))
    for role, color in disabled.items():
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(color))
    return palette


def light_palette() -> QPalette:
    """Return the built-in light palette."""
    return _build_palette(_LIGHT, _LIGHT_DISABLED)


def dark_palette() -> QPalette:
    """Return the built-in dark palette."""
    return _build_palette(_DARK, _DARK_DISABLED)


_THEME_PALETTES = {"Light": (light_palette, Qt.ColorScheme.Light), "Dark": (dark_palette, Qt.ColorScheme.Dark)}
_FUSION = "Fusion"


class BuiltinThemes:
    """Switches a ``QApplication`` between the built-in Light and Dark themes.

    Activate it once with the application, switch with ``set_theme`` and ``deactivate`` it to put back what ``activate`` found.
    ``set_theme`` can be called before ``activate``; the theme is then applied on activation.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._current = "Light"
        self._app: QApplication | None = None
        self._original_style_name = ""
        self._original_palette = QPalette()
        self._original_style_sheet = ""

    @property
    def names(self) -> tuple[str, ...]:
        """The names of the available themes."""
        return tuple(_THEME_PALETTES)

    @property
    def current(self) -> str:
        """The name of the current theme."""
        return self._current

    def activate(self, app: QApplication) -> None:
        """Remember the application's style, palette and style sheet and apply the current theme.

        Args:
            app: The application to theme.

        Raises:
            RuntimeError: If the themes are already active.
        """
        if self._app is not None:
            raise RuntimeError("BuiltinThemes is already active")
        self._original_style_name = app.style().objectName()
        self._original_palette = QPalette(app.palette())
        self._original_style_sheet = app.styleSheet()
        self._app = app
        self._apply(self._current)

    def set_theme(self, name: str) -> None:
        """Switch to a theme.

        Args:
            name: One of ``names``.

        Raises:
            ValueError: If ``name`` is not a built-in theme.
        """
        if name not in _THEME_PALETTES:
            raise ValueError(f"Unknown theme {name!r}; expected one of {self.names}")
        self._current = name
        if self._app is not None:
            self._apply(name)

    def deactivate(self) -> None:
        """Restore the style, palette and style sheet found by ``activate``. Does nothing if not active.

        The style is restored by name. A style that was installed as a ``QStyle`` instance with no name Qt can create again
        cannot be restored this way, and Fusion stays in place.
        """
        app = self._app
        if app is None:
            return
        self._app = None
        if app.style().objectName() != self._original_style_name:
            app.setStyle(self._original_style_name)
        app.setPalette(self._original_palette)
        if app.styleSheet() != self._original_style_sheet:
            app.setStyleSheet(self._original_style_sheet)
        self._reset_color_scheme(app)

    def _apply(self, name: str) -> None:
        app = self._app
        if app is None:
            return
        make_palette, scheme = _THEME_PALETTES[name]
        self._set_color_scheme(app, scheme)
        if app.style().objectName().lower() != _FUSION.lower():
            app.setStyle(_FUSION)
        app.setPalette(make_palette())

    def _set_color_scheme(self, app: QApplication, scheme: Qt.ColorScheme) -> None:
        """Ask Qt to use a colour scheme for platform-drawn parts; a no-op where unsupported."""
        try:
            app.styleHints().setColorScheme(scheme)
        except (AttributeError, RuntimeError):
            self._logger.debug("QStyleHints.setColorScheme is not available", exc_info=True)

    def _reset_color_scheme(self, app: QApplication) -> None:
        try:
            app.styleHints().unsetColorScheme()
        except (AttributeError, RuntimeError):
            self._logger.debug("QStyleHints.unsetColorScheme is not available", exc_info=True)


__all__ = ["BuiltinThemes", "dark_palette", "light_palette"]
