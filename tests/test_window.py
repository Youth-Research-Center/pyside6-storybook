import logging
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFrame, QLabel, QLineEdit, QListWidget, QPushButton, QWidget
from story_files import story_source, write

from pyside6_storybook import BoolControl, IntControl, LoadError, StoryContext, StoryRegistry, load_stories
from pyside6_storybook.gui.controls_panel import NO_CONTROLS_MESSAGE, ControlsPanel
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.window import NO_STORIES_MESSAGE, GalleryWindow
from pyside6_storybook.themes import BuiltinThemes


def _make_window(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> GalleryWindow:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    return window


def _sidebar(window: GalleryWindow) -> QListWidget:
    sidebar = window.findChild(QListWidget, "storySidebar")
    assert sidebar is not None
    return sidebar


def _sidebar_ids(window: GalleryWindow) -> list[str]:
    sidebar = _sidebar(window)
    return [sidebar.item(i).text() for i in range(sidebar.count())]


def test_sidebar_lists_every_story_in_registration_order(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    assert _sidebar_ids(window) == ["Inputs/Button", "Display/Label", "Display/Plain"]


def test_first_story_is_selected_and_previewed_on_start(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)

    assert _sidebar(window).currentRow() == 0
    assert window.current_story_id() == "Inputs/Button"
    heading = window.findChild(QLabel, "previewHeading")
    assert heading is not None
    assert heading.text() == "Inputs/Button"
    preview = window.current_preview_widget()
    assert isinstance(preview, QPushButton)
    assert preview.text() == "Click me"
    surface = window.findChild(QFrame, "previewSurface")
    assert surface is not None
    assert preview.parent() is surface


def test_selecting_a_story_updates_heading_preview_and_controls(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    first_preview = window.current_preview_widget()

    _sidebar(window).setCurrentRow(1)

    heading = window.findChild(QLabel, "previewHeading")
    assert heading is not None
    assert heading.text() == "Display/Label"
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "Light 10"
    assert preview is not first_preview


def test_a_story_without_controls_shows_the_empty_state(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)

    _sidebar(window).setCurrentRow(2)

    panels = [panel for panel in window.findChildren(ControlsPanel) if panel.isVisibleTo(window)]
    assert len(panels) == 1
    empty_label = panels[0].findChild(QLabel, "controlsEmptyState")
    assert empty_label is not None
    assert empty_label.text() == NO_CONTROLS_MESSAGE


def test_changing_a_control_rebuilds_the_preview(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    window.show()
    first = window.current_preview_widget()
    editor = next(e for e in window.findChildren(QLineEdit) if e.isVisibleTo(window))

    editor.selectAll()
    qtbot.keyClicks(editor, "Save")

    second = window.current_preview_widget()
    assert isinstance(second, QPushButton)
    assert second is not first
    assert second.text() == "Save"


def test_switching_theme_rebuilds_the_preview_and_changes_the_palette(qtbot, registry: StoryRegistry, themes: BuiltinThemes, qapp) -> None:
    window = _make_window(qtbot, registry, themes)
    _sidebar(window).setCurrentRow(1)
    first = window.current_preview_widget()
    window_color = qapp.palette().window().color().name()
    switch = window.findChild(QComboBox, "themeSwitch")
    assert switch is not None
    assert [switch.itemText(i) for i in range(switch.count())] == ["Light", "Dark"]
    assert switch.currentText() == "Light"

    switch.setCurrentIndex(1)

    second = window.current_preview_widget()
    assert isinstance(second, QLabel)
    assert second is not first
    assert second.text() == "Dark 10"
    assert themes.current == "Dark"
    assert qapp.palette().window().color().name() != window_color


def test_set_theme_updates_the_switch_and_the_preview(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    first = window.current_preview_widget()

    window.set_theme("Dark")

    switch = window.findChild(QComboBox, "themeSwitch")
    assert switch is not None
    assert switch.currentText() == "Dark"
    assert themes.current == "Dark"
    assert window.current_preview_widget() is not first


def test_set_theme_rejects_unknown_names_without_changing_anything(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    first = window.current_preview_widget()
    with pytest.raises(ValueError, match="Sepia"):
        window.set_theme("Sepia")
    assert window.current_preview_widget() is first
    assert themes.current == "Light"


def test_story_receives_the_args_and_theme_in_its_context(qtbot, themes: BuiltinThemes) -> None:
    contexts: list[StoryContext] = []
    stories = StoryRegistry()

    @stories.story("Recorder", controls=[IntControl("n", 3, 0, 9)])
    def recorder(ctx: StoryContext) -> QWidget:
        contexts.append(ctx)
        return QLabel("r")

    window = _make_window(qtbot, stories, themes)
    window.set_theme("Dark")

    assert [(dict(ctx.args), ctx.theme) for ctx in contexts] == [({"n": 3}, "Light"), ({"n": 3}, "Dark")]


def test_no_method_is_called_on_the_returned_widget(qtbot, themes: BuiltinThemes) -> None:
    class Recording(QLabel):
        def set_tokens(self, tokens: dict) -> None:
            raise AssertionError("set_tokens must not be called")

    stories = StoryRegistry()
    stories.story("Recording")(lambda ctx: Recording("x"))

    window = _make_window(qtbot, stories, themes)

    assert isinstance(window.current_preview_widget(), Recording)


def test_the_previous_preview_widget_is_deleted(qtbot, registry: StoryRegistry, themes: BuiltinThemes, qapp: QApplication) -> None:
    window = _make_window(qtbot, registry, themes)
    first = window.current_preview_widget()
    assert first is not None
    assert shiboken6.isValid(first)

    window.set_theme("Dark")
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not shiboken6.isValid(first)


def test_closing_the_window_releases_the_preview(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    window.show()
    assert window.current_preview_widget() is not None

    window.close()

    assert window.current_preview_widget() is None


def test_an_empty_registry_shows_an_empty_state(qtbot, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, StoryRegistry(), themes)
    window.show()

    assert _sidebar(window).count() == 0
    assert window.current_preview_widget() is None
    assert window.current_story_id() is None
    empty_label = window.findChild(QLabel, "previewEmptyState")
    assert empty_label is not None
    assert empty_label.text() == NO_STORIES_MESSAGE
    assert empty_label.isVisible()
    window.set_theme("Dark")
    assert window.current_preview_widget() is None


def test_the_empty_state_is_hidden_when_there_are_stories(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    window.show()
    empty_label = window.findChild(QLabel, "previewEmptyState")
    assert empty_label is not None
    assert not empty_label.isVisible()


def test_the_chrome_uses_no_fixed_colors(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    window.show()
    assert window.styleSheet() == ""
    for widget in window.findChildren(QWidget):
        assert widget.styleSheet() == "", widget.objectName()


def test_every_widget_has_an_owner(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    _sidebar(window).setCurrentRow(2)
    for widget in window.findChildren(QWidget):
        assert widget.parent() is not None, widget


def test_the_story_list_and_theme_switch_have_accessible_names(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    switch = window.findChild(QComboBox, "themeSwitch")
    assert switch is not None
    assert _sidebar(window).accessibleName() == "Stories"
    assert switch.accessibleName() == "Theme"


def _error_panel(window: GalleryWindow) -> ErrorPanel | None:
    panels = [panel for panel in window.findChildren(ErrorPanel) if panel.isVisibleTo(window)]
    assert len(panels) <= 1
    return panels[0] if panels else None


def _raising(ctx: StoryContext) -> QWidget:
    raise RuntimeError("boom while rendering")


def test_a_story_that_raises_shows_an_error_panel_and_logs_it(qtbot, themes: BuiltinThemes, caplog: pytest.LogCaptureFixture) -> None:
    stories = StoryRegistry()
    stories.story("Good/One")(lambda ctx: QLabel("one"))
    stories.story("Broken/Raises")(_raising)
    window = _make_window(qtbot, stories, themes)
    caplog.set_level(logging.ERROR)

    with qtbot.capture_exceptions() as exceptions:
        _sidebar(window).setCurrentRow(1)

    assert exceptions == []
    panel = _error_panel(window)
    assert panel is not None
    assert panel.title() == "Broken/Raises raised RuntimeError: boom while rendering"
    assert "Traceback" in panel.details()
    assert "boom while rendering" in panel.details()
    assert window.current_preview_widget() is None
    assert any("Broken/Raises" in record.getMessage() and record.exc_info for record in caplog.records)


def test_a_story_that_returns_a_non_widget_shows_an_error_panel(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()
    stories.story("Good/One")(lambda ctx: QLabel("one"))
    stories.story("Broken/None")(lambda ctx: None)  # ty: ignore[invalid-argument-type]
    window = _make_window(qtbot, stories, themes)

    with qtbot.capture_exceptions() as exceptions:
        _sidebar(window).setCurrentRow(1)

    assert exceptions == []
    panel = _error_panel(window)
    assert panel is not None
    assert panel.title() == "Broken/None returned None, expected a QWidget"
    assert window.current_preview_widget() is None


def test_the_next_story_renders_after_an_error(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()
    stories.story("Broken/Raises")(_raising)
    stories.story("Good/One")(lambda ctx: QLabel("one"))
    window = _make_window(qtbot, stories, themes)
    assert _error_panel(window) is not None

    _sidebar(window).setCurrentRow(1)

    assert _error_panel(window) is None
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "one"


def test_the_error_panel_is_replaced_when_the_story_renders_again(qtbot, themes: BuiltinThemes, qapp: QApplication) -> None:
    stories = StoryRegistry()

    @stories.story("Flaky", controls=[BoolControl("fail", default=True)])
    def flaky(ctx: StoryContext) -> QWidget:
        if ctx.args["fail"]:
            raise ValueError("asked to fail")
        return QLabel("rendered")

    window = _make_window(qtbot, stories, themes)
    window.show()
    first_panel = _error_panel(window)
    assert first_panel is not None

    check_box = next(box for box in window.findChildren(QCheckBox) if box.isVisibleTo(window))
    check_box.setChecked(False)
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert _error_panel(window) is None
    assert not shiboken6.isValid(first_panel)
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "rendered"


def test_switching_theme_on_a_broken_story_keeps_the_window_usable(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()
    stories.story("Broken/Raises")(_raising)
    window = _make_window(qtbot, stories, themes)

    with qtbot.capture_exceptions() as exceptions:
        window.set_theme("Dark")

    assert exceptions == []
    assert _error_panel(window) is not None


def _load_errors() -> list[LoadError]:
    return [
        LoadError("stories/broken_story.py", "Importing stories/broken_story.py failed: invalid syntax", "Traceback ...\nSyntaxError: invalid syntax"),
        LoadError("stories/raising_story.py", "Importing stories/raising_story.py failed: boom", "Traceback ...\nRuntimeError: boom"),
    ]


def test_load_errors_get_a_sidebar_entry_after_the_stories(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = GalleryWindow(registry, themes, load_errors=_load_errors())
    qtbot.addWidget(window)

    assert _sidebar_ids(window) == ["Inputs/Button", "Display/Label", "Display/Plain", "Load errors (2)"]
    assert window.current_story_id() == "Inputs/Button"


def test_selecting_the_load_errors_entry_shows_every_error(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = GalleryWindow(registry, themes, load_errors=_load_errors())
    qtbot.addWidget(window)

    _sidebar(window).setCurrentRow(3)

    heading = window.findChild(QLabel, "previewHeading")
    assert heading is not None
    assert heading.text() == "Load errors"
    assert window.current_story_id() is None
    assert window.current_preview_widget() is None
    panel = _error_panel(window)
    assert panel is not None
    assert panel.title() == "2 story sources failed to load"
    for expected in ("stories/broken_story.py", "SyntaxError: invalid syntax", "stories/raising_story.py", "RuntimeError: boom"):
        assert expected in panel.details()
    assert [p for p in window.findChildren(ControlsPanel) if p.isVisibleTo(window)] == []

    _sidebar(window).setCurrentRow(0)
    assert _error_panel(window) is None
    assert isinstance(window.current_preview_widget(), QPushButton)


def test_with_only_load_errors_the_errors_are_shown_on_start(qtbot, themes: BuiltinThemes) -> None:
    window = GalleryWindow(StoryRegistry(), themes, load_errors=_load_errors()[:1])
    qtbot.addWidget(window)
    window.show()

    assert _sidebar_ids(window) == ["Load errors (1)"]
    panel = _error_panel(window)
    assert panel is not None
    assert panel.title() == "1 story source failed to load"
    empty_label = window.findChild(QLabel, "previewEmptyState")
    assert empty_label is not None
    assert not empty_label.isVisible()


def test_one_broken_and_two_working_story_modules(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    """The acceptance case of #8, from real files: the gallery opens, lists the failure, and renders both working stories."""
    write(tmp_path, "stories/a_story.py", story_source("Working/A", "'a'"))
    write(tmp_path, "stories/b_story.py", story_source("Working/B", "'b'"))
    write(tmp_path, "stories/broken_story.py", "def oops(:\n")
    result = load_stories(["stories"], cwd=tmp_path)

    with qtbot.capture_exceptions() as exceptions:
        window = GalleryWindow(result.registry, themes, load_errors=result.errors)
        qtbot.addWidget(window)
        rendered = []
        for row in range(2):
            _sidebar(window).setCurrentRow(row)
            preview = window.current_preview_widget()
            assert isinstance(preview, QLabel)
            rendered.append(preview.text())
        _sidebar(window).setCurrentRow(2)

    assert exceptions == []
    assert rendered == ["a", "b"]
    assert _sidebar_ids(window) == ["Working/A", "Working/B", "Load errors (1)"]
    panel = _error_panel(window)
    assert panel is not None
    assert "SyntaxError" in panel.details()


def test_the_traceback_starts_at_the_story_not_in_the_library(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()
    stories.story("Broken/Raises")(_raising)
    window = _make_window(qtbot, stories, themes)

    panel = _error_panel(window)
    assert panel is not None
    details = panel.details()
    assert "test_window.py" in details
    assert "_raising" in details
    assert "pyside6_storybook" not in details
