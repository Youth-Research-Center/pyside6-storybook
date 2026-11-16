import logging
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)
from story_files import story_source, write

from pyside6_storybook import BoolControl, FloatControl, IntControl, Layout, LoadError, StoryContext, StoryRegistry, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.decorators import fixed_size, frame, padding
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


def test_the_empty_state_sits_at_the_top_of_the_preview(qtbot, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, StoryRegistry(), themes)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    empty_label = window.findChild(QLabel, "previewEmptyState")
    assert empty_label is not None
    surface = window.findChild(QWidget, "previewSurface")
    assert surface is not None
    assert empty_label.height() == empty_label.sizeHint().height()
    assert empty_label.geometry().bottom() < surface.height() // 2


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
        LoadError(
            "stories/broken_story.py",
            "Importing stories/broken_story.py failed: invalid syntax",
            "Traceback ...\nSyntaxError: invalid syntax",
        ),
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


def test_the_controls_section_scrolls_when_there_are_many_controls(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()

    @stories.story("Many", controls=[IntControl(f"value_{index}", 0, 0, 9) for index in range(40)])
    def many(ctx: StoryContext) -> QWidget:
        return QLabel("many")

    window = _make_window(qtbot, stories, themes)
    window.resize(900, 400)
    window.show()
    qtbot.waitExposed(window)
    scroll = window.findChild(QScrollArea, "controlsScroll")
    assert scroll is not None
    host = scroll.widget()
    assert host is not None
    panel = host.findChild(ControlsPanel)
    assert panel is not None

    vertical = scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: vertical.maximum() > 0)
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.widgetResizable()
    assert panel.height() > scroll.viewport().height()


def test_the_controls_section_does_not_scroll_for_a_few_controls(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _make_window(qtbot, registry, themes)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    scroll = window.findChild(QScrollArea, "controlsScroll")
    assert scroll is not None

    assert scroll.verticalScrollBar().maximum() == 0


def test_the_controls_panel_starts_from_the_stories_default_args(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()

    @stories.story("Ratio", controls=[FloatControl("ratio", 1, 0, 2)])
    def ratio(ctx: StoryContext) -> QWidget:
        return QLabel(repr(ctx.args["ratio"]))

    window = _make_window(qtbot, stories, themes)

    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "1.0"


def test_a_variants_panel_starts_at_its_args_and_stays_editable(qtbot, themes: BuiltinThemes) -> None:
    stories = StoryRegistry()

    @stories.story("Inputs/Label/Default", controls=[BoolControl("loud", default=False)])
    def label(ctx: StoryContext) -> QWidget:
        return QLabel("LOUD" if ctx.args["loud"] else "quiet")

    label.variant("Loud", args={"loud": True})
    window = _make_window(qtbot, stories, themes)
    window.show()

    _sidebar(window).setCurrentRow(1)

    assert window.current_story_id() == "Inputs/Label/Loud"
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "LOUD"
    qtbot.waitUntil(lambda: any(box.isVisibleTo(window) for box in window.findChildren(QCheckBox)), timeout=2000)
    check_box = next(box for box in window.findChildren(QCheckBox) if box.isVisibleTo(window))
    assert check_box.isChecked()
    check_box.setChecked(False)
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "quiet"


class _FixedHint(QWidget):
    """A widget with a fixed size hint that can shrink below it, like most real widgets."""

    def __init__(self, width: int, height: int) -> None:
        super().__init__()
        self._hint = QSize(width, height)

    def sizeHint(self) -> QSize:
        return self._hint


def _layout_window(
    qtbot, themes: BuiltinThemes, story_function, *, layout: Layout | str | None, width: int = 700, height: int = 500
) -> GalleryWindow:
    registry = StoryRegistry()
    registry.story("Layout/Story", layout=layout)(story_function)
    window = _make_window(qtbot, registry, themes)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    return window


def _surface(window: GalleryWindow) -> QFrame:
    surface = window.findChild(QFrame, "previewSurface")
    assert surface is not None
    return surface


def _scroll(window: GalleryWindow) -> QScrollArea:
    scroll = window.findChild(QScrollArea, "previewScroll")
    assert scroll is not None
    return scroll


def _preview(window: GalleryWindow) -> QWidget:
    widget = window.current_preview_widget()
    assert widget is not None
    return widget


def _inner_rect(window: GalleryWindow):
    surface = _surface(window)
    return surface.rect().adjusted(10, 10, -10, -10)


def _button(ctx: StoryContext) -> QWidget:
    return QPushButton("Push")


def _expanding(ctx: StoryContext) -> QWidget:
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget


def _small_expanding_horizontally(ctx: StoryContext) -> QWidget:
    widget = QLabel("x")
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


def _wrapping_label(ctx: StoryContext) -> QWidget:
    widget = QLabel("A label wraps long text onto several lines when word wrap is on, instead of growing wider. " * 3)
    widget.setWordWrap(True)
    return widget


def _big(ctx: StoryContext) -> QWidget:
    return _FixedHint(800, 600)


def _small(ctx: StoryContext) -> QWidget:
    return _FixedHint(300, 200)


def test_the_preview_surface_is_the_widget_of_a_scroll_area_and_owns_the_preview(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _button, layout=None)

    assert _scroll(window).widget() is _surface(window)
    assert _scroll(window).widgetResizable()
    assert _preview(window).parent() is _surface(window)
    assert _surface(window).backgroundRole() == _scroll(window).viewport().backgroundRole()


def test_a_story_without_a_layout_uses_the_registry_default(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    registry.default_layout = Layout.FILL
    registry.story("A/B")(_expanding)
    window = _make_window(qtbot, registry, themes)
    window.resize(700, 500)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    assert _preview(window).geometry() == _inner_rect(window)


def test_padded_is_top_aligned_with_the_full_width_for_a_horizontally_expanding_widget(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _small_expanding_horizontally, layout=Layout.PADDED)

    for width, height in ((700, 500), (900, 600)):
        window.resize(width, height)
        QApplication.processEvents()
        inner = _inner_rect(window)
        geometry = _preview(window).geometry()
        assert geometry.x() == inner.x()
        assert geometry.width() == inner.width()
        assert geometry.y() == inner.y()
        assert geometry.height() == _preview(window).sizeHint().height()


def test_padded_stretches_a_button_to_the_full_width_at_its_natural_height(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _button, layout=Layout.PADDED)

    geometry = _preview(window).geometry()

    assert geometry.width() == _inner_rect(window).width()
    assert geometry.height() == _preview(window).sizeHint().height()
    assert geometry.y() == _inner_rect(window).y()


def test_centered_keeps_the_natural_size_and_stays_centered_after_a_resize(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _button, layout=Layout.CENTERED)

    for width, height in ((700, 500), (900, 650), (600, 400)):
        window.resize(width, height)
        QApplication.processEvents()
        surface = _surface(window)
        geometry = _preview(window).geometry()
        assert geometry.size() == _preview(window).sizeHint()
        assert abs(geometry.center().x() - surface.rect().center().x()) <= 1
        assert abs(geometry.center().y() - surface.rect().center().y()) <= 1


def test_fill_gives_an_expanding_widget_the_whole_area_inside_the_margins_before_and_after_a_resize(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _expanding, layout=Layout.FILL)

    for width, height in ((700, 500), (900, 650), (600, 400)):
        window.resize(width, height)
        QApplication.processEvents()
        assert _preview(window).geometry() == _inner_rect(window)


def test_fill_keeps_a_buttons_natural_height_and_centres_it_vertically(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _button, layout=Layout.FILL)

    for width, height in ((700, 500), (900, 650)):
        window.resize(width, height)
        QApplication.processEvents()
        inner = _inner_rect(window)
        geometry = _preview(window).geometry()
        assert geometry.height() == _preview(window).sizeHint().height()
        assert geometry.width() == inner.width()
        assert abs(geometry.center().y() - inner.center().y()) <= 1


@pytest.mark.parametrize("layout", [Layout.PADDED, Layout.CENTERED])
def test_an_oversized_widget_keeps_its_natural_size_and_scrolls_in_padded_and_centered(qtbot, themes: BuiltinThemes, layout: Layout) -> None:
    window = _layout_window(qtbot, themes, _big, layout=layout, width=900, height=500)
    window.resize(900, 500)
    QApplication.processEvents()
    scroll = _scroll(window)

    assert _preview(window).size() == QSize(800, 600)
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBar().maximum() > 0
    assert scroll.verticalScrollBar().maximum() > 0
    window.resize(1000, 560)
    QApplication.processEvents()
    assert _preview(window).size() == QSize(800, 600)
    assert scroll.horizontalScrollBar().maximum() > 0
    assert scroll.verticalScrollBar().maximum() > 0


@pytest.mark.parametrize("layout", [Layout.PADDED, Layout.CENTERED])
def test_a_widget_that_fits_does_not_scroll(qtbot, themes: BuiltinThemes, layout: Layout) -> None:
    window = _layout_window(qtbot, themes, _small, layout=layout)
    scroll = _scroll(window)

    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() == 0
    assert _surface(window).minimumSize() == QSize(320, 220)


def test_fill_has_no_scroll_bars_and_shrinks_the_widget_with_the_pane(qtbot, themes: BuiltinThemes) -> None:
    window = _layout_window(qtbot, themes, _big, layout=Layout.FILL, width=900, height=500)
    scroll = _scroll(window)

    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() == 0
    assert _surface(window).minimumSize() == QSize(0, 0)
    assert _preview(window).geometry() == _inner_rect(window)
    assert _preview(window).width() < 800


def test_switching_from_a_scrolling_story_to_fill_resets_the_surface_minimum(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    registry.story("A/Big", layout=Layout.PADDED)(_big)
    registry.story("B/Fill", layout=Layout.FILL)(_expanding)
    window = _make_window(qtbot, registry, themes)
    window.resize(900, 500)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    assert _surface(window).minimumSize() == QSize(820, 620)

    _sidebar(window).setCurrentRow(1)
    QApplication.processEvents()

    assert _surface(window).minimumSize() == QSize(0, 0)
    assert _scroll(window).horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert _preview(window).geometry() == _inner_rect(window)


def test_the_error_panel_uses_fill_whatever_the_story_declares(qtbot, themes: BuiltinThemes) -> None:
    def failing(ctx: StoryContext) -> QWidget:
        raise RuntimeError("boom")

    for layout in (Layout.CENTERED, Layout.PADDED, Layout.FILL):
        window = _layout_window(qtbot, themes, failing, layout=layout)
        panel = _error_panel(window)
        assert panel is not None
        assert panel.geometry() == _inner_rect(window)
        assert _surface(window).minimumSize() == QSize(0, 0)
        assert _scroll(window).horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert _scroll(window).verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_the_load_errors_view_uses_fill(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = GalleryWindow(registry, themes, load_errors=[LoadError(source="x", message="m", details="d")])
    qtbot.addWidget(window)
    window.resize(700, 500)
    window.show()
    qtbot.waitExposed(window)

    _sidebar(window).setCurrentRow(_sidebar(window).count() - 1)
    QApplication.processEvents()

    panel = _error_panel(window)
    assert panel is not None
    assert panel.geometry() == _inner_rect(window)
    assert _surface(window).minimumSize() == QSize(0, 0)
    assert _scroll(window).verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_a_word_wrapped_label_wraps_in_a_narrow_window_without_a_horizontal_scroll_range(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    registry.story("Display/Padded", layout=Layout.PADDED)(_wrapping_label)
    registry.story("Display/Centered", layout=Layout.CENTERED)(_wrapping_label)
    window = _make_window(qtbot, registry, themes)
    window.resize(500, 300)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    for row in (0, 1):
        _sidebar(window).setCurrentRow(row)
        window.resize(500, 300)
        QApplication.processEvents()
        scroll = _scroll(window)
        preview = _preview(window)
        assert isinstance(preview, QLabel)
        assert preview.hasHeightForWidth()
        assert scroll.horizontalScrollBar().maximum() == 0
        assert preview.width() <= scroll.viewport().width()
        assert preview.height() >= preview.fontMetrics().height() * 2
        assert _surface(window).minimumHeight() == 0


def test_the_label_example_wraps_in_a_narrow_window(qtbot, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    examples = load_stories([EXAMPLES_MODULE]).registry
    window = _make_window(qtbot, examples, themes)
    window.resize(560, 400)
    window.show()
    qtbot.waitExposed(window)
    sidebar = _sidebar(window)
    sidebar.setCurrentRow(_sidebar_ids(window).index("Display/Label"))
    QApplication.processEvents()

    assert _scroll(window).horizontalScrollBar().maximum() == 0
    assert isinstance(_preview(window), QLabel)
    assert _preview(window).height() >= _preview(window).fontMetrics().height() * 2


def test_the_example_layouts_are_centered_for_push_buttons_fill_for_the_table_and_padded_otherwise(stories: StoryRegistry) -> None:
    examples = load_stories([EXAMPLES_MODULE]).registry
    layouts = {story.id: story.layout for story in examples}

    for story_id, layout in layouts.items():
        if story_id.startswith("Buttons/Push Button/"):
            assert layout is Layout.CENTERED, story_id
        elif story_id == "Display/Table":
            assert layout is Layout.FILL
        else:
            assert layout is None, story_id


def _wrap_in_frame(widget: QWidget, ctx: StoryContext) -> QWidget:
    wrapper = QFrame()
    wrapper.setObjectName("decoratorFrame")
    layout = QVBoxLayout(wrapper)
    layout.addWidget(widget)
    return wrapper


def test_current_preview_widget_is_the_undecorated_widget_inside_the_decorated_root(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    registry.decorators.append(_wrap_in_frame)
    registry.story("Group/Story", decorators=[padding(10)])(lambda ctx: QLabel("inner"))
    window = _make_window(qtbot, registry, themes)

    preview = window.current_preview_widget()

    assert isinstance(preview, QLabel)
    assert preview.text() == "inner"
    outer = window.findChild(QFrame, "decoratorFrame")
    assert outer is not None
    assert outer.parentWidget() is _surface(window)
    assert outer.isAncestorOf(preview)
    assert preview.parentWidget() is not outer


def test_rebuilding_deletes_the_decorated_root_and_the_widget(qtbot, themes: BuiltinThemes, qapp: QApplication) -> None:
    registry = StoryRegistry()
    registry.story("Group/Story", decorators=[padding(10), frame()])(lambda ctx: QLabel("inner"))
    window = _make_window(qtbot, registry, themes)
    widget = window.current_preview_widget()
    assert widget is not None
    chain = []
    parent = widget.parentWidget()
    while parent is not None and parent is not _surface(window):
        chain.append(parent)
        parent = parent.parentWidget()
    assert len(chain) == 2

    window.set_theme("Dark")
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert [shiboken6.isValid(item) for item in (widget, *chain)] == [False, False, False]
    assert window.current_preview_widget() is not widget


def test_the_decorated_root_is_placed_with_the_stories_layout(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    registry.story("Group/Story", layout=Layout.CENTERED, decorators=[padding(24), fixed_size(320, 200)])(lambda ctx: QLabel("inner"))
    window = _make_window(qtbot, registry, themes)
    window.resize(900, 650)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    widget = window.current_preview_widget()
    assert widget is not None
    root = widget.parentWidget()
    assert root is not None
    assert root.size() == QSize(368, 248)
    assert widget.geometry().size() == QSize(320, 200)
    assert widget.geometry().topLeft() == QPoint(24, 24)


def test_a_decorator_that_raises_shows_an_error_panel_and_logs_it(qtbot, themes: BuiltinThemes, caplog: pytest.LogCaptureFixture) -> None:
    def broken(widget: QWidget, ctx: StoryContext) -> QWidget:
        raise RuntimeError("decorator boom")

    stories = StoryRegistry()
    stories.story("Good/One")(lambda ctx: QLabel("one"))
    stories.story("Broken/Decorated", decorators=[broken])(lambda ctx: QLabel("x"))
    window = _make_window(qtbot, stories, themes)
    caplog.set_level(logging.ERROR)

    with qtbot.capture_exceptions() as exceptions:
        _sidebar(window).setCurrentRow(1)

    assert exceptions == []
    panel = _error_panel(window)
    assert panel is not None
    assert panel.title().startswith("Broken/Decorated: decorator <function ")
    assert panel.title().endswith("raised RuntimeError: decorator boom")
    assert "decorator boom" in panel.details()
    assert "pyside6_storybook" not in panel.details()
    assert window.current_preview_widget() is None
    assert any("Broken/Decorated" in record.getMessage() and record.exc_info for record in caplog.records)


def test_a_registry_decorator_that_fails_shows_an_error_for_every_story(qtbot, themes: BuiltinThemes) -> None:
    def broken(widget: QWidget, ctx: StoryContext) -> QWidget:
        return QLabel("dropped")

    stories = StoryRegistry()
    stories.decorators.append(broken)
    stories.story("Group/Story")(lambda ctx: QLabel("x"))
    window = _make_window(qtbot, stories, themes)

    panel = _error_panel(window)
    assert panel is not None
    assert panel.title().endswith("returned a widget that does not contain the story's widget")


def _inputs(_ctx: StoryContext) -> QWidget:
    """An unfocused line edit and an unchecked check box, as a form shows them before the user interacts."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    for child in (QLineEdit(widget), QCheckBox("Remember me", widget)):
        child.setObjectName(type(child).__name__)
        child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(child)
    return widget


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_inputs_stand_out_from_the_preview_surface(qtbot, themes: BuiltinThemes, theme: str) -> None:
    registry = StoryRegistry()
    registry.story("Forms/Inputs")(_inputs)
    window = _make_window(qtbot, registry, themes)
    window.set_theme(theme)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    surface = window.findChild(QFrame, "previewSurface")
    preview = window.current_preview_widget()
    assert surface is not None and preview is not None
    edit = preview.findChild(QLineEdit, "QLineEdit")
    check = preview.findChild(QCheckBox, "QCheckBox")
    assert edit is not None and check is not None
    image = window.grab().toImage()
    background = image.pixelColor(surface.mapTo(window, surface.contentsRect().topLeft())).name()

    def strongest(widget: QWidget, rect: QRect) -> float:
        origin = widget.mapTo(window, QPoint(0, 0))
        return max(
            contrast_ratio(image.pixelColor(origin.x() + x, origin.y() + y).name(), background)
            for x in range(rect.left(), rect.right() + 1)
            for y in range(rect.top(), rect.bottom() + 1)
        )

    option = QStyleOptionButton()
    check.initStyleOption(option)
    indicator = check.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, check)
    # The line edit's left edge (frame and fill, away from any text) and the check box's indicator. Before #62 both measured about
    # 1.0 in the Dark theme: the inputs were drawn in the colour of the surface.
    assert strongest(edit, QRect(0, 0, 3, edit.height())) >= 1.25
    assert strongest(check, indicator) >= 1.25
