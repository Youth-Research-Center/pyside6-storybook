"""``BuiltinThemeProvider``: the ``ThemeProvider`` that switches the application between the built-in
Light and Dark themes (Fusion plus an explicit palette) and System (the application's own look).

Qt's own colour-scheme switch (``QStyleHints.setColorScheme``) does nothing on the offscreen platform and its effect depends
on the platform style, so it cannot be the basis of a theme. Each built-in theme instead sets the Fusion style and a complete
``QPalette``, which looks the same on every platform. ``setColorScheme`` is still called on a best-effort basis so that
parts drawn by the platform (title bars, native dialogs) follow the theme where Qt supports it.

The System theme puts back the style, palette and style sheet found at ``activate`` and lets the colour scheme follow the
operating system, unless the application had forced one. Where Qt has no colour-scheme setting (the offscreen platform, for
one), System is whatever Qt defaults to.

An application-wide style sheet takes precedence over the palette for the widgets it styles, so the built-in themes have no
visible effect on those widgets while such a style sheet is set.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QStyleHints
from PySide6.QtWidgets import QApplication

from pyside6_storybook.polishing import polish_all_widgets
from pyside6_storybook.themes.dark_theme import DARK_THEME
from pyside6_storybook.themes.light_theme import LIGHT_THEME

_THEMES = {theme.name: theme for theme in (LIGHT_THEME, DARK_THEME)}

_SYSTEM = "System"
BUILTIN_THEME_NAMES = (*_THEMES, _SYSTEM)
"""The names of the built-in themes, in the order the theme switch lists them. The first one is the default."""
_DARK_LIGHTNESS_LIMIT = 128
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


def palette_color_scheme(palette: QPalette) -> Qt.ColorScheme:
    """Guess a colour scheme from a palette: ``Dark`` when the ``Window`` colour's lightness is below 128, otherwise ``Light``."""
    if palette.color(QPalette.ColorRole.Window).lightness() < _DARK_LIGHTNESS_LIMIT:
        return Qt.ColorScheme.Dark
    return Qt.ColorScheme.Light


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
    """Switches a ``QApplication`` between the built-in Light, Dark and System themes; the default ``ThemeProvider``.

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
        self._forced_scheme: Qt.ColorScheme | None = None
        self._watched_hints: QStyleHints | None = None
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

    def color_scheme(self) -> Qt.ColorScheme:
        """Return the colour scheme of the current theme.

        ``Light`` and ``Dark`` give their own scheme. For System it is the scheme Qt reports, or, when Qt reports ``Unknown``
        (no setting on this platform), a guess from the application palette's ``Window`` colour. Without a ``QApplication``
        System gives ``Unknown``.
        """
        theme = _THEMES.get(self._current)
        if theme is not None:
            return theme.color_scheme
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return Qt.ColorScheme.Unknown
        scheme = self._color_scheme(app)
        return scheme if scheme != Qt.ColorScheme.Unknown else palette_color_scheme(app.palette())

    def on_changed(self, callback: Callable[[], None]) -> None:
        """Register a callback that is called with no arguments after every theme change.

        Args:
            callback: What to call. Callbacks are called in the order they were registered.
        """
        self._callbacks.append(callback)

    def activate(self, app: QApplication) -> None:
        """Remember the application's style, palette, style sheet and font, find out whether it forced a colour scheme, and apply
        the current theme.

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
        self._forced_scheme = self._probe_forced_scheme(app)
        self._app = app
        self._apply(self._current)

    def set_theme(self, name: str) -> None:
        """Switch to a theme.

        Args:
            name: One of ``theme_names``.

        Raises:
            ValueError: If ``name`` is not a built-in theme.
        """
        if name not in BUILTIN_THEME_NAMES:
            raise ValueError(f"Unknown theme {name!r}; expected one of {self.theme_names()}")
        self._current = name
        if self._app is not None:
            self._apply(name)
        self._notify()

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
        self._stop_watching_color_scheme()
        self._restore_original_look(app)
        if app.font() != self._original_font:
            app.setFont(self._original_font)
        self._follow_system_color_scheme(app)

    def _notify(self) -> None:
        for callback in tuple(self._callbacks):
            callback()

    def _apply(self, name: str) -> None:
        app = self._app
        if app is None:
            return
        if name == _SYSTEM:
            self._restore_original_look(app)
            self._follow_system_color_scheme(app)
            self._start_watching_color_scheme(app)
            return
        self._stop_watching_color_scheme()
        theme = _THEMES[name]
        self._set_color_scheme(app, theme.color_scheme)
        if app.style().name().lower() != _FUSION.lower():
            app.setStyle(_FUSION)
        app.setPalette(theme.palette())

    def _restore_original_look(self, app: QApplication) -> None:
        """Put back the style, palette and style sheet found by ``activate``."""
        if self._original_style_name and app.style().name() != self._original_style_name:
            app.setStyle(self._original_style_name)
        app.setPalette(self._original_palette)
        if app.styleSheet() != self._original_style_sheet:
            polish_all_widgets()  # see pyside6_storybook.polishing: a style sheet change with unpolished widgets can crash Qt later
            app.setStyleSheet(self._original_style_sheet)

    def _start_watching_color_scheme(self, app: QApplication) -> None:
        if self._watched_hints is not None:
            return
        try:
            hints = self._style_hints(app)
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)
        except (AttributeError, RuntimeError):
            self._logger.debug("QStyleHints.colorSchemeChanged is not available", exc_info=True)
            return
        self._watched_hints = hints

    def _stop_watching_color_scheme(self) -> None:
        hints, self._watched_hints = self._watched_hints, None
        if hints is None:
            return
        try:
            hints.colorSchemeChanged.disconnect(self._on_color_scheme_changed)
        except (AttributeError, RuntimeError, TypeError):
            self._logger.debug("Disconnecting colorSchemeChanged failed", exc_info=True)

    def _on_color_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        """Notify after the event loop runs: Qt emits the signal before it updates the application palette."""
        QTimer.singleShot(0, self._notify_if_system)

    def _notify_if_system(self) -> None:
        if self._app is not None and self._current == _SYSTEM:
            self._notify()

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

    def _probe_forced_scheme(self, app: QApplication) -> Qt.ColorScheme | None:
        """Find out whether the application forced a colour scheme, and force it again if so.

        Qt cannot say it directly: the override is dropped and the scheme read again. A scheme that changed was forced.
        """
        try:
            hints = self._style_hints(app)
            before = hints.colorScheme()
            hints.unsetColorScheme()
            after = hints.colorScheme()
            if before == after or before == Qt.ColorScheme.Unknown:
                return None
            hints.setColorScheme(before)
        except (AttributeError, RuntimeError):
            self._logger.debug("Probing the colour scheme is not supported", exc_info=True)
            return None
        return before

    def _follow_system_color_scheme(self, app: QApplication) -> None:
        """Drop the scheme a theme set, so the colour scheme follows the system, and force the application's own scheme if it had one."""
        try:
            hints = self._style_hints(app)
            hints.unsetColorScheme()
            if self._forced_scheme is not None:
                hints.setColorScheme(self._forced_scheme)
        except (AttributeError, RuntimeError):
            self._logger.debug("Restoring the colour scheme is not supported", exc_info=True)


__all__ = ["BUILTIN_THEME_NAMES", "BuiltinThemeProvider"]
