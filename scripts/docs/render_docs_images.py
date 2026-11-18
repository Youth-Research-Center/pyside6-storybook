"""Render the images of the docs pages into docs/images/ (development only; not part of the wheel).

    uv run python scripts/docs/render_docs_images.py [--output DIR]

It writes ``gallery.png`` (the gallery on the "Forms/Sign-in Form" example) and ``controls/<type>.png``, one per control type: the editor
as the gallery's controls panel draws it, with its label. Everything is rendered offscreen at twice the display scale in the built-in
Light theme with ``QWidget.grab()``, so the output does not depend on a display. The two images of docs/themes.md come from
``render_theming_images.py``, which renders at the display scale under its own providers.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pyside6_storybook import (
    BoolControl,
    ChoiceControl,
    ColorControl,
    EnumControl,
    FileControl,
    FloatControl,
    IntControl,
    StoryRegistry,
    TextControl,
    load_stories,
)
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.controls import Control
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemeProvider

_DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "images"
_WINDOW_SIZE = (1100, 700)
_STORY = "Forms/Sign-in Form"
_PANEL_WIDTH = 360
_MARGIN = 12
_THEME = "Light"

_CONTROLS: dict[str, Control] = {
    "text": TextControl("title", "Sign in", description="The group box's title."),
    "bool": BoolControl("show_remember", default=True, description="Show the Remember me check box."),
    "choice": ChoiceControl("size", "Medium", ["Small", "Medium", "Large"], description="The button size."),
    "int": IntControl("columns", 3, 1, 12, slider=True, description="How many columns the grid has."),
    "float": FloatControl("opacity", 0.5, 0.0, 1.0, step=0.05, slider=True, description="The opacity of the overlay."),
    "color": ColorControl("accent", "#3584e4", description="The accent colour."),
    "enum": EnumControl("elide", Qt.TextElideMode.ElideRight, description="Where a long text is shortened."),
    "file": FileControl("source", "data/report.csv", filter="Tables (*.csv *.tsv)", description="The file to open."),
}


def _save(widget: QWidget, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not widget.grab().save(str(path), "PNG"):
        raise OSError(f"could not write {path}")


def render_gallery(app: QApplication, registry: StoryRegistry, path: Path) -> None:
    """Render the gallery window showing the sign-in form into a PNG file."""
    provider = BuiltinThemeProvider()
    provider.activate(app)
    window = GalleryWindow(registry, provider)
    try:
        window.set_theme(_THEME)
        window.resize(*_WINDOW_SIZE)
        window.show()
        window.select_story(_STORY)
        app.processEvents()
        # Showing the window gives the search field focus; its frame and caret do not belong in a picture of the gallery.
        focused = app.focusWidget()
        if focused is not None:
            focused.clearFocus()
        app.processEvents()
        _save(window, path)
    finally:
        window.close()
        window.deleteLater()
        provider.deactivate()


def render_controls(app: QApplication, folder: Path) -> None:
    """Render each control type's labelled editor, as the controls panel draws it, into ``folder/<type>.png``."""
    provider = BuiltinThemeProvider()
    provider.activate(app)
    try:
        provider.set_theme(_THEME)
        for name, control in _CONTROLS.items():
            host = QWidget()
            host.setAutoFillBackground(True)
            layout = QVBoxLayout(host)
            layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
            layout.addWidget(ControlsPanel([control], host))
            host.setFixedWidth(_PANEL_WIDTH)
            host.show()
            host.adjustSize()
            app.processEvents()
            focused = app.focusWidget()
            if focused is not None:
                focused.clearFocus()
            app.processEvents()
            try:
                _save(host, folder / f"{name}.png")
            finally:
                host.close()
                host.deleteLater()
    finally:
        provider.deactivate()


def main(argv: Sequence[str] | None = None) -> int:
    """Render the gallery image and the control images."""
    parser = argparse.ArgumentParser(description="Render the images of the docs pages.")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="the folder to write into (default: docs/images)")
    options = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        raise TypeError("a QApplication is required")
    result = load_stories([EXAMPLES_MODULE])
    if result.errors:
        raise RuntimeError(f"the example stories failed to load: {result.errors}")
    output = options.output
    render_gallery(app, result.registry, output / "gallery.png")
    render_controls(app, output / "controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
