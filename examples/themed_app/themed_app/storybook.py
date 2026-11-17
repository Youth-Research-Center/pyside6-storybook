"""Adapts the application's theme manager to the gallery's ``ThemeProvider`` protocol."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from themed_app.theme_manager import ThemeManager


class ThemedAppProvider:
    """Lets the gallery switch the themed application's themes, and restores the application's own look afterwards."""

    def __init__(self) -> None:
        self._manager = ThemeManager()
        self._callbacks: list[Callable[[], None]] = []
        self._app: QApplication | None = None
        self._saved: tuple[str, QPalette, str, QFont] | None = None

    def theme_names(self) -> tuple[str, ...]:
        return self._manager.names()

    def current_theme(self) -> str:
        return self._manager.current()

    def tokens(self) -> Mapping[str, object]:
        return self._manager.tokens()

    def on_changed(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def activate(self, app: QApplication) -> None:
        self._app = app
        self._saved = (app.style().name(), QPalette(app.palette()), app.styleSheet(), QFont(app.font()))
        self._manager.themeChanged.connect(self._notify)  # also fires when the manager changes the theme itself
        self._manager.apply(app, self._manager.current())

    def set_theme(self, name: str) -> None:
        if self._app is None:
            raise RuntimeError("activate the provider before changing the theme")
        self._manager.apply(self._app, name)

    def deactivate(self) -> None:
        self._callbacks.clear()
        app, saved, self._app, self._saved = self._app, self._saved, None, None
        if app is None or saved is None:
            return
        self._manager.themeChanged.disconnect(self._notify)
        style_name, palette, style_sheet, font = saved
        for widget in QApplication.allWidgets():
            widget.ensurePolished()  # before the style sheet changes, as in ThemeManager.apply
        app.setPalette(palette)
        app.setStyleSheet(style_sheet)
        if style_name and app.style().name() != style_name:
            app.setStyle(style_name)
        app.setFont(font)

    def _notify(self) -> None:
        for callback in tuple(self._callbacks):
            callback()


def provider() -> ThemedAppProvider:
    """Return the provider; ``theme_provider = "themed_app.storybook:provider"`` in ``pyproject.toml`` names this function."""
    return ThemedAppProvider()
