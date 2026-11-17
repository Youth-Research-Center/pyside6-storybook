import os
import subprocess
import sys
import textwrap

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from pyside6_storybook.polishing import polish_all_widgets

# Qt crashes in QApplication.setStyleSheet when a widget that was never polished existed while the application style sheet was
# cleared, and was deleted after a style sheet was set again. Each scenario runs in a subprocess, because the crash is a segfault.
_PREAMBLE = """
import gc
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from pyside6_storybook import StoryRegistry
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemeProvider

app = QApplication([])
registry = StoryRegistry()
registry.story("Inputs/Button")(lambda ctx: QPushButton("Button"))
"""


def _run(script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    source = _PREAMBLE + textwrap.dedent(script) + '\nprint("survived")\n'
    return subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=60, env=env, check=False)


def test_a_style_sheet_cleared_while_the_gallery_window_exists_does_not_crash_later() -> None:
    result = _run(
        """
        themes = BuiltinThemeProvider()
        themes.activate(app)
        app.setStyleSheet("QLabel { color: #222222; }")
        window = GalleryWindow(registry, themes)
        app.setStyleSheet("")
        app.setStyleSheet("QLabel { color: #222222; }")
        window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        del window
        gc.collect()
        app.setStyleSheet("QLabel { color: #eeeeee; }")
        """
    )

    assert result.returncode == 0, result.stderr
    assert "survived" in result.stdout


def test_widgets_a_failed_decorator_leaves_for_deletion_are_polished_too() -> None:
    # A failed render hides the story's widget and the decorator's wrapper and deletes them later; they belong to no window.
    result = _run(
        """
        def failing(widget, ctx):
            raise RuntimeError("decorator boom")

        registry.story("Broken/Decorated", decorators=[failing])(lambda ctx: QLabel("Story"))
        themes = BuiltinThemeProvider()
        themes.activate(app)
        window = GalleryWindow(registry, themes)
        assert window.select_story("Broken/Decorated")
        app.setStyleSheet("QLabel { color: #222222; }")
        app.setStyleSheet("")
        app.setStyleSheet("QLabel { color: #222222; }")
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        app.setStyleSheet("QLabel { color: #eeeeee; }")
        """
    )

    assert result.returncode == 0, result.stderr
    assert "survived" in result.stdout


def test_activating_the_themes_under_an_application_style_sheet_does_not_crash_later() -> None:
    # Activating reads the style under the style sheet by clearing the style sheet for a moment.
    result = _run(
        """
        app.setStyleSheet("QLabel { color: #222222; }")
        label = QLabel("Never shown")
        themes = BuiltinThemeProvider()
        themes.activate(app)
        del label
        gc.collect()
        app.setStyleSheet("QLabel { color: #eeeeee; }")
        themes.deactivate()
        """
    )

    assert result.returncode == 0, result.stderr
    assert "survived" in result.stdout


def test_polish_all_widgets_polishes_widgets_that_were_never_shown(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.ensurePolished()
    late_child = QLabel("Added after the parent was polished", parent)
    assert not late_child.testAttribute(Qt.WidgetAttribute.WA_WState_Polished)

    polish_all_widgets()

    assert late_child.testAttribute(Qt.WidgetAttribute.WA_WState_Polished)
    assert all(widget.testAttribute(Qt.WidgetAttribute.WA_WState_Polished) for widget in QApplication.allWidgets())
