import functools
import inspect
import sys
import types
from enum import Enum
from pathlib import Path

import pytest
from conftest import show_active
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from story_files import write

from pyside6_storybook import (
    BoolControl,
    ChoiceControl,
    ColorControl,
    EnumControl,
    FileControl,
    FloatControl,
    IntControl,
    Story,
    StoryContext,
    StoryRegistry,
    TextControl,
    load_stories,
)
from pyside6_storybook.gui import docs_panel
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.docs_panel import NO_CONTROLS_MESSAGE, NO_SOURCE_MESSAGE, VARIANT_CAPTION, DocsPanel, controls_rows
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemes


class Mode(Enum):
    FAST = 1
    SLOW = 2


def _build(ctx: StoryContext) -> QWidget:
    return QLabel("x")


def _flush() -> None:
    """Delete the widgets a panel replaced, which ``deleteLater()`` leaves findable until the event loop runs."""
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _panel(qtbot, story: Story, registry: StoryRegistry) -> DocsPanel:
    panel = DocsPanel()
    qtbot.addWidget(panel)
    panel.show_story(story, registry)
    _flush()
    return panel


def _label(panel: DocsPanel, name: str) -> QLabel:
    label = panel.findChild(QLabel, name)
    assert label is not None
    return label


def _cell(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def _header(table: QTableWidget, column: int) -> str:
    item = table.horizontalHeaderItem(column)
    assert item is not None
    return item.text()


def _headings(panel: DocsPanel) -> list[str]:
    return [label.text() for label in panel.findChildren(QLabel, "docsHeading")]


def _register(registry: StoryRegistry, story_id: str, **kwargs) -> Story:
    return registry.story(story_id, **kwargs)(_build)


def _window(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> GalleryWindow:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    return window


def _window_panel(window: GalleryWindow) -> DocsPanel:
    panel = window.findChild(DocsPanel)
    assert panel is not None
    return panel


def test_story_function_is_the_decorated_function() -> None:
    registry = StoryRegistry()

    def build(ctx: StoryContext) -> QWidget:
        return QLabel("x")

    story = registry.story("A/B")(build)
    variant = story.variant("C")

    assert story.function is build
    assert variant.function is build
    with pytest.raises(AttributeError):
        story.function = _build  # ty: ignore[invalid-assignment]


def test_controls_rows_for_every_control_type() -> None:
    controls = (
        TextControl("title", "Hi"),
        TextControl("body", "a\nb", multiline=True),
        BoolControl("enabled", default=True),
        ChoiceControl("size", "m", ["s", "m", "l"]),
        IntControl("count", 5, 0, 10),
        IntControl("stepped", 50, 0, 100, step=5),
        FloatControl("ratio", 0.5, 0.0, 1.0, step=0.1, decimals=2),
        ColorControl("tint", "#336699"),
        ColorControl("glass", "#33669980", alpha=True),
        EnumControl("mode", Mode.SLOW),
        FileControl("path"),
        FileControl("image", Path("a.png"), filter="Images (*.png)"),
    )
    values = {control.name: control.coerce(control.default) for control in controls}

    rows = controls_rows(controls, values)

    assert rows == [
        ("title", "text", "'Hi'", ""),
        ("body", "multiline text", "'a\\nb'", ""),
        ("enabled", "bool", "True", ""),
        ("size", "choice", "m", "s, m, l"),
        ("count", "int", "5", "0..10"),
        ("stepped", "int", "50", "0..100, step 5"),
        ("ratio", "float", "0.5", "0.0..1.0, step 0.1, decimals 2"),
        ("tint", "colour", "#336699", ""),
        ("glass", "colour", "#33669980", "with alpha"),
        ("mode", "Mode", "SLOW", "FAST, SLOW"),
        ("path", "file", "(none)", ""),
        ("image", "file", str(Path("a.png")), "Images (*.png)"),
    ]


def test_a_variant_shows_its_own_starting_values_and_says_so(qtbot) -> None:
    registry = StoryRegistry()
    base = _register(registry, "Box/Default", controls=[IntControl("size", 1, 0, 9), BoolControl("on", default=False)])
    variant = base.variant("Big", args={"size": 7, "on": True})

    assert controls_rows(variant.controls, variant.default_args()) == [
        ("size", "int", "7", "0..9"),
        ("on", "bool", "True", ""),
    ]
    variant_panel = _panel(qtbot, variant, registry)
    base_panel = _panel(qtbot, base, registry)
    table = variant_panel.findChild(QTableWidget, "docsControlsTable")
    assert table is not None
    assert _cell(table, 0, 2) == "7"
    assert _label(variant_panel, "docsVariantCaption").text() == VARIANT_CAPTION
    assert base_panel.findChild(QLabel, "docsVariantCaption") is None


def test_the_table_lists_the_controls_read_only(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default", controls=[IntControl("size", 1, 0, 9)])

    panel = _panel(qtbot, story, registry)
    table = panel.findChild(QTableWidget, "docsControlsTable")

    assert table is not None
    assert [_header(table, column) for column in range(table.columnCount())] == [
        "Name",
        "Type",
        "Default",
        "Range or options",
    ]
    assert [[_cell(table, 0, column) for column in range(4)]] == [["size", "int", "1", "0..9"]]
    assert table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers


def test_a_story_without_controls_says_so(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default")

    panel = _panel(qtbot, story, registry)

    assert _label(panel, "docsNoControls").text() == NO_CONTROLS_MESSAGE
    assert panel.findChild(QTableWidget) is None


def test_module_and_story_docstrings_are_shown(qtbot, stories: StoryRegistry, tmp_path: Path) -> None:
    write(
        tmp_path,
        "docs_stories/button_story.py",
        '''
        """Buttons of the toolkit."""

        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import story


        @story("Button/Default")
        def build(ctx):
            """Shows a button.

            Second paragraph."""
            return QLabel("x")
        ''',
    )
    result = load_stories(["docs_stories"], cwd=tmp_path)

    panel = _panel(qtbot, result.registry.get("Button/Default"), result.registry)

    module_doc = _label(panel, "docsModuleDoc")
    story_doc = _label(panel, "docsStoryDoc")
    assert module_doc.text() == "Buttons of the toolkit."
    assert story_doc.text() == "Shows a button.\n\nSecond paragraph."
    assert module_doc.textFormat() == Qt.TextFormat.PlainText
    assert story_doc.textFormat() == Qt.TextFormat.PlainText
    assert module_doc.wordWrap()
    assert story_doc.wordWrap()
    assert "Component description" in _headings(panel)
    assert "Story description" in _headings(panel)


def test_there_is_no_heading_for_an_empty_docstring(qtbot, stories: StoryRegistry, tmp_path: Path) -> None:
    write(
        tmp_path,
        "bare_stories/plain_story.py",
        """
        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import story


        @story("Plain/Default")
        def build(ctx):
            return QLabel("x")
        """,
    )
    result = load_stories(["bare_stories"], cwd=tmp_path)

    panel = _panel(qtbot, result.registry.get("Plain/Default"), result.registry)

    assert panel.findChild(QLabel, "docsModuleDoc") is None
    assert panel.findChild(QLabel, "docsStoryDoc") is None
    assert _headings(panel) == ["Controls", "Source"]


def test_docstring_labels_are_selectable_by_keyboard_and_mouse(qtbot, stories: StoryRegistry, tmp_path: Path) -> None:
    write(
        tmp_path,
        "select_stories/doc_story.py",
        '''
        """Module text."""

        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import story


        @story("Doc/Default")
        def build(ctx):
            """Story text."""
            return QLabel("x")
        ''',
    )
    result = load_stories(["select_stories"], cwd=tmp_path)
    panel = _panel(qtbot, result.registry.get("Doc/Default"), result.registry)

    for name in ("docsModuleDoc", "docsStoryDoc"):
        flags = _label(panel, name).textInteractionFlags()
        assert flags & Qt.TextInteractionFlag.TextSelectableByKeyboard
        assert flags & Qt.TextInteractionFlag.TextSelectableByMouse


def test_the_source_is_shown_in_a_read_only_fixed_font_view(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default")

    panel = _panel(qtbot, story, registry)

    view = panel.findChild(QPlainTextEdit, "docsSource")
    assert view is not None
    assert view.toPlainText() == inspect.getsource(_build)
    assert panel.source_text() == inspect.getsource(_build)
    assert view.isReadOnly()
    assert view.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap
    assert view.font().pointSizeF() == pytest.approx(QApplication.font().pointSizeF())
    assert view.font().family() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def test_copy_puts_the_source_on_the_clipboard(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default")
    panel = _panel(qtbot, story, registry)
    QApplication.clipboard().setText("before")

    button = panel.findChild(QPushButton, "docsCopyButton")
    assert button is not None
    assert button.text() == "Copy"
    assert not button.icon().isNull()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert QApplication.clipboard().text() == inspect.getsource(_build)


def test_a_story_built_from_a_partial_has_no_source(qtbot) -> None:
    registry = StoryRegistry()
    story = registry.story("Box/Default")(functools.partial(_build))

    panel = _panel(qtbot, story, registry)

    assert _label(panel, "docsNoSource").text() == NO_SOURCE_MESSAGE
    assert panel.findChild(QPlainTextEdit) is None
    assert panel.findChild(QPushButton, "docsCopyButton") is None
    assert panel.source_text() == ""


def test_a_story_whose_source_cannot_be_read_has_no_source(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default")

    def fail(_: object) -> str:
        raise OSError("source code not available")

    monkeypatch.setattr(docs_panel.inspect, "getsource", fail)

    panel = _panel(qtbot, story, registry)

    assert _label(panel, "docsNoSource").text() == NO_SOURCE_MESSAGE


def test_a_variant_shares_its_bases_source(qtbot) -> None:
    registry = StoryRegistry()
    base = _register(registry, "Box/Default")
    variant = base.variant("Other")

    assert _panel(qtbot, variant, registry).source_text() == inspect.getsource(_build)


def _siblings_registry() -> tuple[StoryRegistry, Story, Story, Story]:
    registry = StoryRegistry()
    base = _register(registry, "Inputs/Button/Default")
    disabled = base.variant("Disabled")
    wide = base.variant("Wide")
    _register(registry, "Inputs/Button/Unrelated")
    _register(registry, "Inputs/Other/Default")
    return registry, base, disabled, wide


def test_siblings_list_the_base_and_the_variants(qtbot) -> None:
    registry, base, disabled, wide = _siblings_registry()

    panel = _panel(qtbot, base, registry)

    assert "Stories of Inputs/Button" in _headings(panel)
    links = panel.findChildren(QLabel, "docsSiblingLink")
    assert [label.accessibleName() for label in links] == ["Open Inputs/Button/Disabled", "Open Inputs/Button/Wide"]
    assert _label(panel, "docsSiblingCurrent").text() == "Default (this story)"
    assert disabled.id in links[0].text()
    assert wide.id in links[1].text()


def test_the_current_story_is_not_linked_and_a_variant_lists_its_base(qtbot) -> None:
    registry, _, disabled, _ = _siblings_registry()

    panel = _panel(qtbot, disabled, registry)

    assert _label(panel, "docsSiblingCurrent").text() == "Disabled (this story)"
    assert [label.accessibleName() for label in panel.findChildren(QLabel, "docsSiblingLink")] == [
        "Open Inputs/Button/Default",
        "Open Inputs/Button/Wide",
    ]
    link = panel.findChildren(QLabel, "docsSiblingLink")[0]
    assert link.textFormat() == Qt.TextFormat.RichText
    assert link.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByKeyboard
    assert link.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByMouse


def test_a_story_without_siblings_has_no_list(qtbot) -> None:
    registry, *_ = _siblings_registry()

    panel = _panel(qtbot, registry.get("Inputs/Other/Default"), registry)

    assert panel.findChild(QLabel, "docsSiblingLink") is None
    assert panel.findChild(QLabel, "docsSiblingCurrent") is None


def test_activating_a_link_requests_that_story(qtbot) -> None:
    registry, base, *_ = _siblings_registry()
    panel = _panel(qtbot, base, registry)
    link = panel.findChildren(QLabel, "docsSiblingLink")[1]
    requested: list[str] = []
    panel.storyRequested.connect(requested.append)

    link.linkActivated.emit("Inputs/Button/Wide")

    assert requested == ["Inputs/Button/Wide"]


def test_activating_a_link_selects_that_story_in_the_window(qtbot, themes: BuiltinThemes) -> None:
    registry, base, *_ = _siblings_registry()
    window = _window(qtbot, registry, themes)
    window.select_story(base.id)
    _flush()
    link = next(label for label in _window_panel(window).findChildren(QLabel, "docsSiblingLink") if "Wide" in label.text())

    href = link.text().split('"')[1]
    link.linkActivated.emit(href)
    _flush()

    assert window.current_story_id() == "Inputs/Button/Wide"
    assert _label(_window_panel(window), "docsSiblingCurrent").text() == "Wide (this story)"


def test_the_preview_pane_has_canvas_and_docs_tabs_in_document_mode(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _window(qtbot, registry, themes)

    tabs = window.findChild(QTabWidget, "previewTabs")

    assert tabs is not None
    assert tabs.documentMode()
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Canvas", "Docs"]
    assert tabs.widget(0) is window.findChild(QWidget, "previewScroll")
    assert tabs.widget(1) is window.findChild(QWidget, "docsScroll")
    docs_scroll = tabs.widget(1)
    assert isinstance(docs_scroll, QScrollArea)
    assert docs_scroll.widget() is _window_panel(window)


def test_the_docs_follow_the_selection(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _window(qtbot, registry, themes)
    panel = _window_panel(window)
    assert 'QPushButton(str(ctx.args["text"]))' in panel.source_text()

    window.select_story("Display/Plain")
    _flush()

    assert 'QLabel("plain")' in panel.source_text()
    assert 'QPushButton(str(ctx.args["text"]))' not in panel.source_text()
    assert _label(panel, "docsNoControls").text() == NO_CONTROLS_MESSAGE


def test_a_control_change_does_not_rebuild_the_docs(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = _window(qtbot, registry, themes)
    window.select_story("Display/Label")
    _flush()
    panel = _window_panel(window)
    table = panel.findChild(QTableWidget, "docsControlsTable")
    assert table is not None
    controls_panel = window.findChild(ControlsPanel)
    assert controls_panel is not None
    spin_box = controls_panel.findChild(QSpinBox)
    assert spin_box is not None

    spin_box.setValue(spin_box.value() + 1)
    _flush()

    assert panel.findChild(QTableWidget, "docsControlsTable") is table


def test_the_docs_refresh_after_set_registry(qtbot, themes: BuiltinThemes) -> None:
    old = StoryRegistry()
    old.story("Box/Default", controls=[IntControl("size", 1, 0, 9)])(_build)
    new = StoryRegistry()
    new.story("Box/Default", controls=[IntControl("size", 2, 0, 99), BoolControl("on", default=True)])(_build)
    window = _window(qtbot, old, themes)
    old_table = _window_panel(window).findChild(QTableWidget, "docsControlsTable")
    assert old_table is not None
    assert old_table.rowCount() == 1

    window.set_registry(new)
    _flush()

    table = _window_panel(window).findChild(QTableWidget, "docsControlsTable")
    assert table is not None
    assert [_cell(table, row, 3) for row in range(table.rowCount())] == ["0..99", ""]
    assert _cell(table, 0, 2) == "2"


def test_the_docs_are_empty_without_a_story(qtbot, themes: BuiltinThemes) -> None:
    window = _window(qtbot, StoryRegistry(), themes)

    panel = _window_panel(window)

    assert panel.findChild(QLabel, "docsHeading") is None
    assert panel.source_text() == ""


# Review fixes


def _documented(ctx: StoryContext) -> QWidget:
    """Story text."""
    return QLabel("x")


def test_headings_are_plain_text_even_with_markup_in_the_component_name(qtbot) -> None:
    registry = StoryRegistry()
    base = _register(registry, "Box <b>Bold/Default")
    base.variant("Other")

    panel = _panel(qtbot, base, registry)

    headings = panel.findChildren(QLabel, "docsHeading")
    assert all(heading.textFormat() == Qt.TextFormat.PlainText for heading in headings)
    assert "Stories of Box <b>Bold" in [heading.text() for heading in headings]


@pytest.mark.usefixtures("restore_window_activation")
def test_tab_reaches_a_description_label(qtbot) -> None:
    registry = StoryRegistry()
    story = registry.story("Box/Default")(_documented)
    window = QWidget()
    qtbot.addWidget(window)
    layout = QVBoxLayout(window)
    field = QLineEdit(window)
    panel = DocsPanel(window)
    layout.addWidget(field)
    layout.addWidget(panel)
    panel.show_story(story, registry)
    _flush()
    show_active(qtbot, window)
    field.setFocus()
    qtbot.waitUntil(field.hasFocus, timeout=2000)

    qtbot.keyClick(field, Qt.Key.Key_Tab)

    assert QApplication.focusWidget() is _label(panel, "docsStoryDoc")


def test_the_controls_table_is_at_least_as_wide_as_its_columns(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default", controls=[TextControl("text", "long " * 40)])
    panel = _panel(qtbot, story, registry)
    panel.resize(200, 400)
    panel.show()

    table = panel.findChild(QTableWidget, "docsControlsTable")
    assert table is not None
    columns = sum(table.columnWidth(column) for column in range(table.columnCount()))
    assert columns > 300
    assert table.minimumWidth() >= columns + table.verticalHeader().width() + 2 * table.frameWidth()


def test_selecting_many_stories_keeps_at_most_one_copy_binding(qtbot, themes: BuiltinThemes) -> None:
    registry = StoryRegistry()
    for index in range(20):
        _register(registry, f"Group/Story{index}")
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    window.show()
    _flush()
    baseline = window._icons.binding_count()

    for index in range(20):
        window.select_story(f"Group/Story{index}")
        _flush()

    assert window._icons.binding_count() <= baseline
    assert len(window.findChildren(QPushButton, "docsCopyButton")) == 1


def test_the_source_view_follows_a_pixel_sized_application_font(qtbot) -> None:
    registry = StoryRegistry()
    story = _register(registry, "Box/Default")
    original = QApplication.font()
    font = QApplication.font()
    font.setPixelSize(30)
    QApplication.setFont(font)
    try:
        assert QApplication.font().pointSizeF() <= 0
        panel = _panel(qtbot, story, registry)
        view = panel.findChild(QPlainTextEdit, "docsSource")
        assert view is not None
        assert view.font().pixelSize() == 30
    finally:
        QApplication.setFont(original)


def test_a_partial_story_describes_the_module_of_the_wrapped_function(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("docs_partial_module")
    module.__doc__ = "The real module."
    monkeypatch.setitem(sys.modules, "docs_partial_module", module)

    def build(ctx: StoryContext, extra: int = 1) -> QWidget:
        return QLabel("x")

    build.__module__ = "docs_partial_module"
    registry = StoryRegistry()
    story = registry.story("Box/Default")(functools.partial(functools.partial(build, extra=2)))

    panel = _panel(qtbot, story, registry)

    assert _label(panel, "docsModuleDoc").text() == "The real module."


def test_a_partial_story_without_a_real_module_has_no_component_description(qtbot) -> None:
    def build(ctx: StoryContext, extra: int = 1) -> QWidget:
        return QLabel("x")

    build.__module__ = "docs_module_that_is_not_loaded"
    registry = StoryRegistry()
    story = registry.story("Box/Default")(functools.partial(build, extra=2))

    panel = _panel(qtbot, story, registry)

    assert panel.findChild(QLabel, "docsModuleDoc") is None
    assert "Component description" not in _headings(panel)
