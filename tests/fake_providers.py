"""Theme providers for tests: a small one that sets a style sheet, a palette and a font, and two that misbehave."""

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from string import Template

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


AGGRESSIVE_STYLE_SHEET = Path(__file__).parent / "fixtures" / "aggressive.qss"

_AGGRESSIVE_THEMES = {
    "Midnight": {
        "window": "#10151c",
        "base": "#1b2330",
        "text": "#e8ecf2",
        "button": "#2a3a52",
        "accent": "#4f8cff",
        "selection": "#1e88e5",
        "palette_highlight": "#303030",
    },
    "Daylight": {
        "window": "#f3ecd8",
        "base": "#fffaf0",
        "text": "#1a1a1a",
        "button": "#e2d6b5",
        "accent": "#8a5a00",
        "selection": "#ffb300",
        "palette_highlight": "#303030",
    },
}


class AggressiveProvider(StyleSheetProvider):
    """A provider whose style sheet restyles the whole gallery: "Midnight" (dark) and "Daylight" (light).

    The style sheet is ``fixtures/aggressive.qss``. ``selection`` chooses how it colours the selected sidebar row: ``"highlight"``
    sets ``selection-background-color``, which reaches the option palette's ``Highlight``; ``"item"`` sets
    ``QTreeView::item:selected { background }``, which does not, and the palette's own ``Highlight`` is then a different colour;
    ``"both"`` keeps both rules. The palette is the matching one with white ``HighlightedText``, which is unreadable on either theme's
    selection colour, so only the sidebar's selection delegate can make the text readable.
    """

    def __init__(self, *, selection: str = "both") -> None:
        super().__init__()
        self.current = "Midnight"
        self.selection = selection

    def theme_names(self) -> tuple[str, ...]:
        return tuple(_AGGRESSIVE_THEMES)

    def set_theme(self, name: str) -> None:
        self.calls.append(name)
        if name not in _AGGRESSIVE_THEMES:
            raise ValueError(name)
        self.current = name
        self._apply()
        self.simulate_external_change()

    def tokens(self) -> Mapping[str, object]:
        return dict(_AGGRESSIVE_THEMES[self.current])

    def style_sheet(self) -> str:
        """Return the style sheet of the current theme, with the selection rules of ``selection`` only."""
        text = AGGRESSIVE_STYLE_SHEET.read_text(encoding="utf-8")
        for form in ("highlight", "item"):
            if self.selection not in (form, "both"):
                text = re.sub(rf"/\* begin {form} \*/.*?/\* end {form} \*/", "", text, flags=re.DOTALL)
        return Template(text).safe_substitute(_AGGRESSIVE_THEMES[self.current])

    def _apply(self) -> None:
        assert self._app is not None
        colors = _AGGRESSIVE_THEMES[self.current]
        palette = QPalette()
        highlight = colors["selection"] if self.selection == "highlight" else colors["palette_highlight"]
        for role, color in (
            (QPalette.ColorRole.Window, colors["window"]),
            (QPalette.ColorRole.WindowText, colors["text"]),
            (QPalette.ColorRole.Base, colors["base"]),
            (QPalette.ColorRole.AlternateBase, colors["window"]),
            (QPalette.ColorRole.Text, colors["text"]),
            (QPalette.ColorRole.Button, colors["button"]),
            (QPalette.ColorRole.ButtonText, colors["text"]),
            (QPalette.ColorRole.PlaceholderText, colors["text"]),
            (QPalette.ColorRole.Highlight, highlight),
            (QPalette.ColorRole.HighlightedText, "#ffffff"),
        ):
            palette.setColor(role, QColor(color))
        self._app.setPalette(palette)
        self._app.setStyleSheet(self.style_sheet())
