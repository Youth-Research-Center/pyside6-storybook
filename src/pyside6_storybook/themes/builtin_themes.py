"""``BuiltinThemes``: switches the application between the built-in Light and Dark themes (Fusion plus an explicit palette).

Qt's own colour-scheme switch (``QStyleHints.setColorScheme``) does nothing on the offscreen platform and its effect depends
on the platform style, so it cannot be the basis of a theme. Each built-in theme instead sets the Fusion style and a complete
``QPalette``, which looks the same on every platform. ``setColorScheme`` is still called on a best-effort basis so that
parts drawn by the platform (title bars, native dialogs) follow the theme where Qt supports it.

An application-wide style sheet takes precedence over the palette for the widgets it styles, so the built-in themes have no
visible effect on those widgets while such a style sheet is set.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QStyleHints
from PySide6.QtWidgets import QApplication

from pyside6_storybook.themes.dark_theme import DARK_THEME
from pyside6_storybook.themes.light_theme import LIGHT_THEME

_THEMES = {theme.name: theme for theme in (LIGHT_THEME, DARK_THEME)}
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
        self._original_color_scheme = Qt.ColorScheme.Unknown

    @property
    def names(self) -> tuple[str, ...]:
        """The names of the available themes."""
        return tuple(_THEMES)

    @property
    def current(self) -> str:
        """The name of the current theme."""
        return self._current

    def activate(self, app: QApplication) -> None:
        """Remember the application's style, palette, style sheet and colour scheme and apply the current theme.

        Args:
            app: The application to theme.

        Raises:
            RuntimeError: If the themes are already active.
        """
        if self._app is not None:
            raise RuntimeError("BuiltinThemes is already active")
        self._original_style_name = self._underlying_style_name(app)
        self._original_palette = QPalette(app.palette())
        self._original_style_sheet = app.styleSheet()
        self._original_color_scheme = self._color_scheme(app)
        self._app = app
        self._apply(self._current)

    def set_theme(self, name: str) -> None:
        """Switch to a theme.

        Args:
            name: One of ``names``.

        Raises:
            ValueError: If ``name`` is not a built-in theme.
        """
        if name not in _THEMES:
            raise ValueError(f"Unknown theme {name!r}; expected one of {self.names}")
        self._current = name
        if self._app is not None:
            self._apply(name)

    def deactivate(self) -> None:
        """Restore the style, palette, style sheet and colour scheme found by ``activate``. Does nothing if not active.

        The style is restored by name. A style that was installed as a ``QStyle`` instance with no name Qt can create again
        cannot be restored this way, and Fusion stays in place.
        """
        app = self._app
        if app is None:
            return
        self._app = None
        if self._original_style_name and app.style().name() != self._original_style_name:
            app.setStyle(self._original_style_name)
        app.setPalette(self._original_palette)
        if app.styleSheet() != self._original_style_sheet:
            app.setStyleSheet(self._original_style_sheet)
        self._restore_color_scheme(app)

    def _apply(self, name: str) -> None:
        app = self._app
        if app is None:
            return
        theme = _THEMES[name]
        self._set_color_scheme(app, theme.color_scheme)
        if app.style().name().lower() != _FUSION.lower():
            app.setStyle(_FUSION)
        app.setPalette(theme.palette())

    @staticmethod
    def _underlying_style_name(app: QApplication) -> str:
        """Return the name of the application's style, also while an application style sheet is set.

        With a style sheet, ``app.style()`` is Qt's style sheet style, whose name is empty; the style sheet is cleared for a
        moment to read the name of the style underneath it.
        """
        name = app.style().name()
        style_sheet = app.styleSheet()
        if name or not style_sheet:
            return name
        app.setStyleSheet("")
        try:
            return app.style().name()
        finally:
            app.setStyleSheet(style_sheet)

    def _style_hints(self, app: QApplication) -> QStyleHints:
        return app.styleHints()

    def _color_scheme(self, app: QApplication) -> Qt.ColorScheme:
        try:
            return self._style_hints(app).colorScheme()
        except (AttributeError, RuntimeError):
            self._logger.debug("QStyleHints.colorScheme is not available", exc_info=True)
            return Qt.ColorScheme.Unknown

    def _set_color_scheme(self, app: QApplication, scheme: Qt.ColorScheme) -> None:
        """Ask Qt to use a colour scheme for platform-drawn parts; a no-op where unsupported."""
        try:
            self._style_hints(app).setColorScheme(scheme)
        except (AttributeError, RuntimeError):
            self._logger.debug("QStyleHints.setColorScheme is not available", exc_info=True)

    def _restore_color_scheme(self, app: QApplication) -> None:
        """Put back the colour scheme the application had before ``activate``.

        Qt cannot tell whether that scheme was forced by the application or followed the system. The override set by the themes
        is dropped first, which restores a scheme that followed the system; only when the result still differs from the
        original is the original forced again.
        """
        try:
            hints = self._style_hints(app)
            hints.unsetColorScheme()
            original = self._original_color_scheme
            if original != Qt.ColorScheme.Unknown and hints.colorScheme() != original:
                hints.setColorScheme(original)
        except (AttributeError, RuntimeError):
            self._logger.debug("Restoring the colour scheme is not supported", exc_info=True)


__all__ = ["BuiltinThemes"]
