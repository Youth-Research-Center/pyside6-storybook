import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QListWidget

from pyside6_storybook import LoadError, StoryRegistry
from pyside6_storybook.app import run
from pyside6_storybook.themes import DARK_THEME
from pyside6_storybook.window import GalleryWindow


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


def test_run_with_an_empty_registry_opens_the_empty_gallery(qapp: QApplication, restore_application_look: None) -> None:
    QTimer.singleShot(0, qapp.quit)
    assert run(StoryRegistry(), argv=[]) == 0


def test_run_starts_in_the_requested_theme_and_restores_the_palette(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    palette_before = QPalette(qapp.palette())
    seen: dict[str, object] = {}

    def inspect_and_quit() -> None:
        (window,) = [widget for widget in qapp.topLevelWidgets() if isinstance(widget, GalleryWindow)]
        switch = window.findChild(QComboBox, "themeSwitch")
        sidebar = window.findChild(QListWidget, "storySidebar")
        assert switch is not None and sidebar is not None
        sidebar.setCurrentRow(1)
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


def test_run_rejects_an_unknown_theme_without_changing_the_application(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
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
        sidebar = window.findChild(QListWidget, "storySidebar")
        assert sidebar is not None
        seen["entries"] = [sidebar.item(row).text() for row in range(sidebar.count())]
        qapp.quit()

    QTimer.singleShot(0, inspect_and_quit)
    errors = (LoadError("stories/broken_story.py", "Importing stories/broken_story.py failed: boom"),)

    assert run(registry, argv=["pyside6-storybook"], load_errors=errors) == 0
    assert seen["entries"] == ["Inputs/Button", "Display/Label", "Display/Plain", "Load errors (1)"]
