import pytest
import shiboken6
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QLabel, QLineEdit, QListWidget, QPushButton, QWidget

from pyside6_storybook import IntControl, StoryContext, StoryRegistry
from pyside6_storybook.controls_panel import NO_CONTROLS_MESSAGE, ControlsPanel
from pyside6_storybook.themes import BuiltinThemes
from pyside6_storybook.window import NO_STORIES_MESSAGE, GalleryWindow


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


def test_a_story_that_returns_a_non_widget_raises_type_error_naming_the_story(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()
    stories.story("Good/One")(lambda ctx: QLabel("one"))
    stories.story("Broken/Story")(lambda ctx: None)  # type: ignore[arg-type, return-value]
    window = _make_window(qtbot, stories, themes)

    with qtbot.capture_exceptions() as exceptions:
        _sidebar(window).setCurrentRow(1)

    assert len(exceptions) == 1
    exception_type, exception, _traceback = exceptions[0]
    assert exception_type is TypeError
    assert "Broken/Story" in str(exception)
    assert window.current_preview_widget() is None


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
