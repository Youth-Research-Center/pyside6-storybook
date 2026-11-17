import functools
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from story_files import story_source, write

from pyside6_storybook import LoadError, StoryRegistry, load_stories
from pyside6_storybook.app import run
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.gui.sidebar import StorySidebar
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import DARK_THEME
from pyside6_storybook.themes.provider_loader import load_theme_provider


def test_run_shows_the_window_themes_the_app_and_restores_it(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    palette_before = QPalette(qapp.palette())
    seen: dict[str, object] = {}

    def inspect_and_quit() -> None:
        windows = [widget for widget in qapp.topLevelWidgets() if isinstance(widget, GalleryWindow)]
        seen["window_count"] = len(windows)
        if windows:
            seen["visible"] = windows[0].isVisible()
            seen["story"] = windows[0].current_story_id()
            seen["size"] = (windows[0].width(), windows[0].height())
        seen["style"] = qapp.style().objectName()
        seen["window_color"] = qapp.palette().window().color().name()
        qapp.quit()

    QTimer.singleShot(0, inspect_and_quit)
    exit_code = run(registry, argv=["pyside6-storybook"])

    assert exit_code == 0
    assert seen["window_count"] == 1
    assert seen["visible"] is True
    assert seen["story"] == "Inputs/Button"
    assert seen["size"] == (1100, 700)
    assert str(seen["style"]).lower() == "fusion"
    assert seen["window_color"] == "#f0f0f0"
    assert qapp.palette() == palette_before


_RUN_TWICE = """
import sys
sys.path.insert(0, {tests!r})
from fake_providers import StyleSheetProvider
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from pyside6_storybook import StoryRegistry, run

app = QApplication([])
registry = StoryRegistry()
registry.story("Inputs/Button")(lambda ctx: QPushButton("Button"))


def failing(ctx):
    raise RuntimeError("boom")


registry.story("Broken/Story")(failing)


def use_the_gallery():
    window = next(w for w in QApplication.topLevelWidgets() if type(w).__name__ == "GalleryWindow" and w.isVisible())
    window.select_story("Broken/Story")
    window.select_story("Inputs/Button")
    window.set_theme("Ink")
    app.quit()


for _ in range(3):
    QTimer.singleShot(0, use_the_gallery)
    assert run(registry, argv=[], theme_provider=StyleSheetProvider()) == 0
print("survived")
"""


def test_run_can_be_called_again_with_a_provider_that_sets_a_style_sheet() -> None:
    # run() used to leave the closed window pending deletion while the provider restored the style sheet; deleting it later crashed
    # Qt in the next setStyleSheet (#80). The scenario runs in a subprocess because the crash is a segfault.
    tests = str(Path(__file__).resolve().parent)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", _RUN_TWICE.format(tests=tests)], capture_output=True, text=True, timeout=60, env=env, check=False
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "survived" in result.stdout


def test_run_leaves_later_event_loops_working(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    QTimer.singleShot(0, qapp.quit)
    assert run(registry, argv=["pyside6-storybook"]) == 0
    qapp.processEvents()  # delivers anything run() left posted, as pytest-qt does between tests

    loop = QEventLoop()
    QTimer.singleShot(0, functools.partial(loop.exit, 7))
    assert loop.exec() == 7


def test_run_with_an_empty_registry_opens_the_empty_gallery(qapp: QApplication, restore_application_look: None) -> None:
    QTimer.singleShot(0, qapp.quit)
    assert run(StoryRegistry(), argv=[]) == 0


def test_run_starts_in_the_requested_theme_and_restores_the_palette(
    qapp: QApplication, restore_application_look: None, registry: StoryRegistry
) -> None:
    palette_before = QPalette(qapp.palette())
    seen: dict[str, object] = {}

    def inspect_and_quit() -> None:
        (window,) = [widget for widget in qapp.topLevelWidgets() if isinstance(widget, GalleryWindow)]
        switch = window.findChild(QComboBox, "sbkThemeSwitch")
        assert switch is not None
        assert window.select_story("Display/Label")
        preview = window.current_preview_widget()
        assert isinstance(preview, QLabel)
        seen["switch"] = switch.currentText()
        seen["window_color"] = qapp.palette().window().color().name()
        seen["story_theme"] = preview.text()
        qapp.quit()

    QTimer.singleShot(0, inspect_and_quit)

    assert run(registry, argv=["pyside6-storybook"], theme="Dark") == 0
    assert seen == {
        "switch": "Dark",
        "window_color": DARK_THEME.colors[QPalette.ColorRole.Window].lower(),
        "story_theme": "Dark 10",
    }
    assert qapp.palette() == palette_before


def test_run_rejects_an_unknown_theme_without_changing_the_application(
    qapp: QApplication, restore_application_look: None, registry: StoryRegistry
) -> None:
    palette_before = QPalette(qapp.palette())
    style_before = qapp.style().name()
    windows_before = set(qapp.topLevelWidgets())
    QTimer.singleShot(0, qapp.quit)  # ends the event loop if run() ever stops rejecting the theme, so the test fails instead of hanging

    with pytest.raises(ValueError, match="Sepia"):
        run(registry, argv=["pyside6-storybook"], theme="Sepia")

    assert qapp.palette() == palette_before
    assert qapp.style().name() == style_before
    assert not [widget for widget in set(qapp.topLevelWidgets()) - windows_before if isinstance(widget, GalleryWindow)]


def test_run_lists_load_errors_in_the_gallery(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    seen: dict[str, object] = {}

    def inspect_and_quit() -> None:
        (window,) = [widget for widget in qapp.topLevelWidgets() if isinstance(widget, GalleryWindow)]
        sidebar = window.findChild(StorySidebar)
        assert sidebar is not None
        seen["entries"] = [*sidebar.visible_story_ids(), sidebar.load_errors_label()]
        qapp.quit()

    QTimer.singleShot(0, inspect_and_quit)
    errors = (LoadError("stories/broken_story.py", "Importing stories/broken_story.py failed: boom"),)

    assert run(registry, argv=["pyside6-storybook"], load_errors=errors) == 0
    assert seen["entries"] == ["Inputs/Button", "Display/Label", "Display/Plain", "Load errors (1)"]


def test_run_keeps_the_modules_a_provider_imports_in_activate(
    qapp: QApplication, restore_application_look: None, tmp_path: Path, stories: StoryRegistry
) -> None:
    write(tmp_path, "lazy_manager.py", "MANAGER = object()\n")
    write(
        tmp_path,
        "lazy_theming.py",
        """
class Provider:
    def theme_names(self):
        return ("Paper",)

    def current_theme(self):
        return "Paper"

    def activate(self, app):
        import lazy_manager

        self.manager = lazy_manager.MANAGER

    def set_theme(self, name):
        pass

    def on_changed(self, callback):
        pass

    def deactivate(self):
        pass


provider = Provider()
""",
    )
    write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "str(id(__import__('lazy_manager').MANAGER))"))
    sys.path.insert(0, str(tmp_path))
    loaded = load_theme_provider("lazy_theming:provider")
    provider = loaded.provider
    assert "lazy_manager" not in sys.modules
    result = load_stories(("stories",), cwd=tmp_path)
    assert result.errors == ()
    session = ReloadSession(("stories",), cwd=tmp_path, initial=result, keep=loaded.modules)
    seen: dict[str, object] = {}

    # The stories import the manager only when a story is built, after activate() imported it.
    def reload_and_quit() -> None:
        seen["manager"] = sys.modules["lazy_manager"]
        write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "str(id(__import__('lazy_manager').MANAGER)) + 'x'"))
        seen["accepted"] = session.reload().accepted
        seen["after"] = sys.modules["lazy_manager"]
        qapp.quit()

    QTimer.singleShot(0, reload_and_quit)
    assert run(result.registry, argv=["pyside6-storybook"], reload=session, theme_provider=provider) == 0

    assert seen["accepted"] is True
    assert seen["after"] is seen["manager"]
    assert sys.modules["lazy_manager"].MANAGER is sys.modules["lazy_theming"].provider.manager


def test_run_without_a_reload_session_does_not_need_one(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    QTimer.singleShot(0, qapp.quit)
    assert run(registry, argv=["pyside6-storybook"], reload=None) == 0
