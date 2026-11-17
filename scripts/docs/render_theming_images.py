"""Render the two screenshots of docs/theming.md into docs/images/ (development only; not part of the wheel).

    uv run python scripts/docs/render_theming_images.py

Both show the gallery under a provider that applies a dark application style sheet. The first leaves the palette alone, so the
gallery's own text, drawn from palette roles, is unreadable on the dark backgrounds; the second sets a matching palette too.
The windows are rendered offscreen at a fixed size with ``QWidget.grab()``, so the output does not depend on a display.
"""

import os
import sys
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from pyside6_storybook import StoryRegistry, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.gui.window import GalleryWindow

_OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "images"
_SIZE = (1100, 700)
_STORY = "Buttons/Push Button/Default"
_BACKGROUND, _TEXT, _BUTTON, _ACCENT = "#14181f", "#e6e9ee", "#2a3342", "#7ab8ff"
_STYLE_SHEET = f"""
QWidget {{ background-color: {_BACKGROUND}; }}
QPushButton, QComboBox, QTabBar::tab {{ background-color: {_BUTTON}; }}
QLineEdit, QTreeView, QSpinBox {{ background-color: #1c222b; }}
"""


class DarkStyleSheetProvider:
    """A theme provider with one theme that sets a dark style sheet, and a matching palette only when asked to."""

    def __init__(self, *, with_palette: bool) -> None:
        self._with_palette = with_palette
        self._callbacks: list[Callable[[], None]] = []
        self._app: QApplication | None = None
        self._saved: tuple[QPalette, str, QFont] | None = None

    def theme_names(self) -> tuple[str, ...]:
        return ("Ink",)

    def current_theme(self) -> str:
        return "Ink"

    def on_changed(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def set_theme(self, name: str) -> None:
        if name != "Ink":
            raise ValueError(name)

    def activate(self, app: QApplication) -> None:
        self._app = app
        self._saved = (QPalette(app.palette()), app.styleSheet(), QFont(app.font()))
        if self._with_palette:
            app.setPalette(_dark_palette())
        app.setStyleSheet(_STYLE_SHEET)

    def deactivate(self) -> None:
        self._callbacks.clear()
        if self._app is None or self._saved is None:
            return
        palette, style_sheet, font = self._saved
        for widget in QApplication.allWidgets():
            widget.ensurePolished()
        self._app.setPalette(palette)
        self._app.setStyleSheet(style_sheet)
        self._app.setFont(font)
        self._app = self._saved = None


def _dark_palette() -> QPalette:
    palette = QPalette()
    role = QPalette.ColorRole
    colors = {
        role.Window: _BACKGROUND,
        role.WindowText: _TEXT,
        role.Base: "#1c222b",
        role.AlternateBase: _BUTTON,
        role.Text: _TEXT,
        role.Button: _BUTTON,
        role.ButtonText: _TEXT,
        role.PlaceholderText: "#9aa4b2",
        role.Highlight: _ACCENT,
        role.HighlightedText: "#0b0e12",
        role.Accent: _ACCENT,
        role.Mid: "#37414f",
    }
    for palette_role, color in colors.items():
        palette.setColor(palette_role, QColor(color))
    return palette


def render(app: QApplication, registry: StoryRegistry, path: Path, *, with_palette: bool) -> None:
    """Render the gallery under the provider into a PNG file."""
    provider = DarkStyleSheetProvider(with_palette=with_palette)
    look = (QPalette(app.palette()), app.styleSheet())
    provider.activate(app)
    window = GalleryWindow(registry, provider)
    try:
        window.resize(*_SIZE)
        window.show()
        window.select_story(_STORY)
        app.processEvents()
        if not window.grab().save(str(path), "PNG"):
            raise OSError(f"could not write {path}")
    finally:
        window.close()
        window.deleteLater()
        provider.deactivate()
        if (QPalette(app.palette()), app.styleSheet()) != look:
            raise RuntimeError("the application's look was not restored")


def main() -> int:
    """Render both images."""
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        raise TypeError("a QApplication is required")
    result = load_stories([EXAMPLES_MODULE])
    if result.errors:
        raise RuntimeError(f"the example stories failed to load: {result.errors}")
    registry = result.registry
    _OUTPUT.mkdir(parents=True, exist_ok=True)
    render(app, registry, _OUTPUT / "theming-no-palette.png", with_palette=False)
    render(app, registry, _OUTPUT / "theming-with-palette.png", with_palette=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
