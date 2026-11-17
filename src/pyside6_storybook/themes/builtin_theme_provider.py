"""``BuiltinThemeProvider``: the ``ThemeProvider`` that switches the application between the built-in
Light and Dark themes (Fusion plus an explicit palette).

Qt's own colour-scheme switch (``QStyleHints.setColorScheme``) does nothing on the offscreen platform and its effect depends
on the platform style, so it cannot be the basis of a theme. Each built-in theme instead sets the Fusion style and a complete
``QPalette``, which looks the same on every platform. ``setColorScheme`` is still called on a best-effort basis so that
parts drawn by the platform (title bars, native dialogs) follow the theme where Qt supports it.

An application-wide style sheet takes precedence over the palette for the widgets it styles, so the built-in themes have no
visible effect on those widgets while such a style sheet is set.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QStyleHints
from PySide6.QtWidgets import QApplication

from pyside6_storybook.polishing import polish_all_widgets
from pyside6_storybook.themes.dark_theme import DARK_THEME
from pyside6_storybook.themes.light_theme import LIGHT_THEME

_THEMES = {theme.name: theme for theme in (LIGHT_THEME, DARK_THEME)}

BUILTIN_THEME_NAMES = tuple(_THEMES)
"""The names of the built-in themes, in the order the theme switch lists them. The first one is the default."""
_FUSION = "Fusion"
_ROLE = QPalette.ColorRole
_TOKEN_ROLES = {
    "window": _ROLE.Window,
    "window_text": _ROLE.WindowText,
    "base": _ROLE.Base,
    "alternate_base": _ROLE.AlternateBase,
    "text": _ROLE.Text,
    "button": _ROLE.Button,
    "button_text": _ROLE.ButtonText,
    "highlight": _ROLE.Highlight,
    "highlighted_text": _ROLE.HighlightedText,
    "accent": _ROLE.Accent,
    "border": _ROLE.Mid,
    "placeholder_text": _ROLE.PlaceholderText,
}


def underlying_style_name(app: QApplication) -> str:
    """Return the name of the application's style, also while an application style sheet is set.

    With a style sheet, ``app.style()`` is Qt's style sheet style, whose name is empty; the style sheet is cleared for a moment to read
    the name of the style underneath it.
    """
    name = app.style().name()
    style_sheet = app.styleSheet()
    if name or not style_sheet:
        return name
    polish_all_widgets()  # see pyside6_storybook.polishing: clearing the style sheet with unpolished widgets can crash Qt later
    app.setStyleSheet("")
    try:
        return app.style().name()
    finally:
        app.setStyleSheet(style_sheet)

class BuiltinThemeProvider:
    """Switches a ``QApplication`` between the built-in Light and Dark themes; the default ``ThemeProvider``.

    Activate it once with the application, switch with ``set_theme`` and ``deactivate`` it to put back what ``activate`` found.
    ``set_theme`` can be called before ``activate``; the theme is then applied on activation. ``set_theme`` calls the callbacks
    registered with ``on_changed`` before it returns.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._current = "Light"
        self._app: QApplication | None = None
        self._original_style_name = ""
        self._original_palette = QPalette()
        self._original_style_sheet = ""
        self._original_font = QFont()
        self._original_color_scheme = Qt.ColorScheme.Unknown
        self._callbacks: list[Callable[[], None]] = []

    def theme_names(self) -> tuple[str, ...]:
        """Return the names of the available themes."""
        return BUILTIN_THEME_NAMES

    def current_theme(self) -> str:
        """Return the name of the current theme."""
        return self._current

    def tokens(self) -> Mapping[str, object]:
        """Return the design tokens: ``#rrggbb`` strings read from the application palette's Active group.

        The tokens are ``window``, ``window_text``, ``base``, ``alternate_base``, ``text``, ``button``, ``button_text``, ``highlight``,
        ``highlighted_text``, ``accent``, ``border`` (the ``Mid`` role) and ``placeholder_text``. Without a ``QApplication`` the
        mapping is empty.
        """
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return {}
        palette = app.palette()
        return {name: palette.color(QPalette.ColorGroup.Active, role).name() for name, role in _TOKEN_ROLES.items()}

    def on_changed(self, callback: Callable[[], None]) -> None:
        """Register a callback that is called with no arguments after every theme change.

        Args:
            callback: What to call. Callbacks are called in the order they were registered.
        """
        self._callbacks.append(callback)

    def activate(self, app: QApplication) -> None:
        """Remember the application's style, palette, style sheet, font and colour scheme and apply the current theme.

        Args:
            app: The application to theme.

        Raises:
            RuntimeError: If the themes are already active.
        """
        if self._app is not None:
            raise RuntimeError("BuiltinThemeProvider is already active")
        self._original_style_name = underlying_style_name(app)
        self._original_palette = QPalette(app.palette())
        self._original_style_sheet = app.styleSheet()
        self._original_font = QFont(app.font())
        self._original_color_scheme = self._color_scheme(app)
        self._app = app
        self._apply(self._current)

    def set_theme(self, name: str) -> None:
        """Switch to a theme.

        Args:
            name: One of ``theme_names``.

        Raises:
            ValueError: If ``name`` is not a built-in theme.
        """
        if name not in _THEMES:
            raise ValueError(f"Unknown theme {name!r}; expected one of {self.theme_names()}")
        self._current = name
        if self._app is not None:
            self._apply(name)
        for callback in tuple(self._callbacks):
            callback()

    def deactivate(self) -> None:
        """Restore the style, palette, style sheet, font and colour scheme found by ``activate`` and clear the callbacks.

        Does nothing if not active.

        The style is restored by name. A style that was installed as a ``QStyle`` instance with no name Qt can create again
        cannot be restored this way, and Fusion stays in place.
        """
        app = self._app
        if app is None:
            return
        self._app = None
        self._callbacks.clear()
        if self._original_style_name and app.style().name() != self._original_style_name:
            app.setStyle(self._original_style_name)
        app.setPalette(self._original_palette)
        if app.styleSheet() != self._original_style_sheet:
            polish_all_widgets()  # see pyside6_storybook.polishing: a style sheet change with unpolished widgets can crash Qt later
            app.setStyleSheet(self._original_style_sheet)
        if app.font() != self._original_font:
            app.setFont(self._original_font)
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


__all__ = ["BUILTIN_THEME_NAMES", "BuiltinThemeProvider"]
