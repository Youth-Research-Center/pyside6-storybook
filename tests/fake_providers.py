"""Theme providers for tests: a small one that sets a style sheet, a palette and a font, and two that misbehave."""

from collections.abc import Callable, Mapping

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

_THEMES = {"Paper": ("#fdf6e3", "#222222", 10), "Ink": ("#101418", "#e8e8e8", 12)}


class StyleSheetProvider:
    """A provider with the themes "Paper" and "Ink"; each sets an application style sheet, a matching palette and a font."""

    def __init__(self) -> None:
        self.current = "Paper"
        self.calls: list[str] = []
        self._callbacks: list[Callable[[], None]] = []
        self._app: QApplication | None = None
        self._saved: tuple[QPalette, str, QFont] | None = None

    def theme_names(self) -> tuple[str, ...]:
        return tuple(_THEMES)

    def current_theme(self) -> str:
        return self.current

    def on_changed(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def activate(self, app: QApplication) -> None:
        self._app, self._saved = app, (QPalette(app.palette()), app.styleSheet(), QFont(app.font()))
        self._apply()

    def set_theme(self, name: str) -> None:
        self.calls.append(name)
        if name not in _THEMES:
            raise ValueError(name)
        self.current = name
        self._apply()
        self.simulate_external_change()

    def simulate_external_change(self) -> None:
        """Call the callbacks as a provider does when its own theme manager changes the theme."""
        for callback in list(self._callbacks):
            callback()

    def tokens(self) -> Mapping[str, object]:
        return {"background": _THEMES[self.current][0]}

    def deactivate(self) -> None:
        if self._app is not None and self._saved is not None:
            self._restore(*self._saved)
        self._app, self._saved = None, None
        self._callbacks.clear()

    def _restore(self, palette: QPalette, style_sheet: str, font: QFont) -> None:
        assert self._app is not None
        self._app.setPalette(palette)
        self._app.setStyleSheet(style_sheet)
        self._app.setFont(font)

    def _apply(self) -> None:
        assert self._app is not None
        background, text, size = _THEMES[self.current]
        palette = QPalette()
        for role, color in ((QPalette.ColorRole.Window, background), (QPalette.ColorRole.WindowText, text), (QPalette.ColorRole.Base, background)):
            palette.setColor(role, QColor(color))
        font = QFont(self._app.font())
        font.setPointSize(size)
        self._app.setPalette(palette)
        self._app.setStyleSheet(f"QLabel {{ color: {text}; }}")
        self._app.setFont(font)


class RaisingProvider(StyleSheetProvider):
    """A provider whose ``set_theme`` and ``tokens`` raise ``RuntimeError("boom")``."""

    def set_theme(self, name: str) -> None:
        raise RuntimeError("boom")

    def tokens(self) -> Mapping[str, object]:
        raise RuntimeError("boom")


class LeakyProvider(StyleSheetProvider):
    """A provider that does not restore the font in ``deactivate``."""

    def _restore(self, palette: QPalette, style_sheet: str, font: QFont) -> None:
        assert self._app is not None
        self._app.setPalette(palette)
        self._app.setStyleSheet(style_sheet)
