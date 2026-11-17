"""Keyboard navigation and accessibility of the whole gallery window: tab order, panes, shortcuts, focus, contrast and large fonts."""

import functools
from collections import Counter
from typing import TypeVar

import pytest
from conftest import show_active
from icon_testing import strongest_pixel
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAccessible, QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QTabBar,
    QTableWidget,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook import BoolControl, IntControl, StoryContext, StoryRegistry, TextControl
from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.gui.canvas import Canvas
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.reload_status import ReloadStatus
from pyside6_storybook.gui.sidebar import StorySidebar
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import DARK_THEME, LIGHT_THEME, BuiltinThemeProvider

pytestmark = pytest.mark.usefixtures("restore_window_activation")

_W = TypeVar("_W", bound=QWidget)
_NO_LIMIT = 16_777_215
_THEMES = [LIGHT_THEME, DARK_THEME]


def _registry() -> StoryRegistry:
    """Three stories; the first has controls and a story widget with every kind of input the shortcuts must leave alone."""
    stories = StoryRegistry()

    @stories.story("Inputs/Button", controls=[TextControl("text", "Click me"), BoolControl("enabled", default=True), IntControl("count", 3, 1, 9)])
    def button(ctx: StoryContext) -> QWidget:
        """A button with a few inputs beside it."""
        box = QWidget()
        layout = QVBoxLayout(box)
        push = QPushButton(str(ctx.args["text"]), box)
        push.setAccessibleName("Story button")
        field = QLineEdit(box)
        field.setAccessibleName("Story field")
        spin = QSpinBox(box)
        spin.setAccessibleName("Story spin")
        editable = QComboBox(box)
        editable.setEditable(True)
        editable.setAccessibleName("Story editable combo")
        fixed = QComboBox(box)
        fixed.addItems(["one", "two"])
        fixed.setAccessibleName("Story combo")
        for widget in (push, field, spin, editable, fixed):
            layout.addWidget(widget)
        return box

    @stories.story("Display/Label", controls=[IntControl("size", 10, 1, 50)])
    def label(ctx: StoryContext) -> QWidget:
        """A label."""
        return QLabel(f"{ctx.theme} {ctx.args['size']}")

    @stories.story("Display/Plain")
    def plain(ctx: StoryContext) -> QWidget:
        return QLabel("plain")

    return stories


def _make(qtbot, themes: BuiltinThemeProvider, registry: StoryRegistry | None = None) -> GalleryWindow:
    window = GalleryWindow(registry if registry is not None else _registry(), themes)
    qtbot.addWidget(window)
    window.resize(1100, 700)
    show_active(qtbot, window)
    return window


def _child(window: QWidget, kind: type[_W], name: str) -> _W:
    found = window.findChild(kind, name)
    assert found is not None, name
    return found


def _name(widget: QWidget) -> str:
    """The name assistive technology reads: the accessible name property, else what the accessibility interface derives."""
    if widget.accessibleName().strip():
        return widget.accessibleName()
    interface = QAccessible.queryAccessibleInterface(widget)
    return interface.text(QAccessible.Text.Name).strip() if interface is not None else ""


def _focus(qtbot, widget: QWidget) -> None:
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(lambda: QApplication.focusWidget() is widget or widget.hasFocus(), timeout=5000)


def _focused_name() -> str:
    widget = QApplication.focusWidget()
    assert widget is not None
    return _name(widget)


def _tab(qtbot, *, backwards: bool = False) -> str:
    widget = QApplication.focusWidget()
    assert widget is not None
    if backwards:
        qtbot.keyClick(widget, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    else:
        qtbot.keyClick(widget, Qt.Key.Key_Tab)
    return _focused_name()


def _key(qtbot, key: Qt.Key, modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    widget = QApplication.focusWidget()
    assert widget is not None
    qtbot.keyClick(widget, key, modifier)


_TAB_ORDER = [
    "Search stories",
    "Stories",
    "Preview tabs",
    "Background",
    "Size",
    "Zoom out",
    "Zoom in",
    "Reset zoom",
    "Preview of Inputs/Button",
    "Story button",
    "Story field",
    "Story spin",
    "Story editable combo",
    "Story combo",
    "Theme",
    "Controls and actions tabs",
    "Text",
    "Enabled",
    "Count",
]


# Tab order


def test_tab_visits_the_panes_in_reading_order_and_wraps_to_the_search(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _child(window, StorySidebar, "sbkStorySidebar").focus_search()
    qtbot.waitUntil(lambda: _focused_name() == "Search stories", timeout=5000)

    visited = [_focused_name()]
    visited += [_tab(qtbot) for _ in range(len(_TAB_ORDER) - 1)]

    assert visited == _TAB_ORDER
    assert _tab(qtbot) == "Search stories"


def test_shift_tab_walks_the_same_order_backwards(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _child(window, StorySidebar, "sbkStorySidebar").focus_search()
    qtbot.waitUntil(lambda: _focused_name() == "Search stories", timeout=5000)

    visited = [_focused_name()] + [_tab(qtbot, backwards=True) for _ in range(len(_TAB_ORDER) - 1)]

    assert visited == [_TAB_ORDER[0], *reversed(_TAB_ORDER[1:])]


def test_the_tab_order_follows_the_story_when_it_changes(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    window.select_story("Display/Label")
    qtbot.wait(50)
    _focus(qtbot, _child(window, QScrollArea, "sbkPreviewScroll"))

    assert _focused_name() == "Preview of Display/Label"
    assert [_tab(qtbot) for _ in range(4)] == ["Theme", "Controls and actions tabs", "Size", "Search stories"]


def test_the_tab_order_follows_the_docs_tab(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    tabs = _child(window, QTabWidget, "sbkPreviewTabs")
    tabs.setCurrentIndex(1)
    _focus(qtbot, tabs.tabBar())

    first = _tab(qtbot)

    assert first == "Docs"


# Panes


def test_the_panes_and_the_preview_area_have_accessible_names(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    sidebar = _child(window, StorySidebar, "sbkStorySidebar")
    preview_pane = _child(window, QTabWidget, "sbkPreviewTabs").parentWidget()
    side_pane = _child(window, QTabWidget, "sbkSideTabs").parentWidget()
    assert preview_pane is not None
    assert side_pane is not None

    assert sidebar.accessibleName() == "Story list"
    assert preview_pane.accessibleName() == "Preview"
    assert side_pane.accessibleName() == "Controls and actions"
    scroll = _child(window, QScrollArea, "sbkPreviewScroll")
    assert scroll.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert scroll.accessibleName() == "Preview of Inputs/Button"
    window.select_story("Display/Plain")
    assert scroll.accessibleName() == "Preview of Display/Plain"


def test_the_preview_area_is_named_without_a_story(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes, StoryRegistry())

    assert _child(window, QScrollArea, "sbkPreviewScroll").accessibleName() == "Preview"


def test_f6_cycles_through_the_panes_and_returns_to_the_last_focused_widget(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _child(window, StorySidebar, "sbkStorySidebar").focus_search()
    qtbot.waitUntil(lambda: _focused_name() == "Search stories", timeout=5000)
    _focus(qtbot, _child(window, QTreeView, "sbkStoryTree"))

    _key(qtbot, Qt.Key.Key_F6)
    assert _focused_name() == "Preview tabs"
    _tab(qtbot)
    _tab(qtbot)
    assert _focused_name() == "Size"
    _key(qtbot, Qt.Key.Key_F6)
    assert _focused_name() == "Theme"
    _key(qtbot, Qt.Key.Key_F6)
    assert _focused_name() == "Stories"
    _key(qtbot, Qt.Key.Key_F6)
    assert _focused_name() == "Size"
    _key(qtbot, Qt.Key.Key_F6)
    assert _focused_name() == "Theme"


def test_shift_f6_cycles_backwards(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _child(window, QTreeView, "sbkStoryTree"))

    _key(qtbot, Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier)
    assert _focused_name() == "Theme"
    _key(qtbot, Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier)
    assert _focused_name() == "Preview tabs"
    _key(qtbot, Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier)
    assert _focused_name() == "Stories"


def test_f6_falls_back_to_the_first_widget_when_the_remembered_one_is_gone(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _story_input(window, QPushButton, "Story button"))
    _focus(qtbot, _child(window, QTreeView, "sbkStoryTree"))
    window.select_story("Display/Label")

    _key(qtbot, Qt.Key.Key_F6)

    assert _focused_name() == "Preview tabs"


# Accessible names


def _chrome_focusables(window: GalleryWindow) -> list[QWidget]:
    """The visible, enabled widgets Tab can stop at, outside the story's own widget and the internals that forward focus."""
    canvas = window.findChild(Canvas)
    assert canvas is not None
    story_root = canvas.placed_widget()
    found = []
    for widget in window.findChildren(QWidget):
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus or not widget.isVisible() or not widget.isEnabled():
            continue
        if widget.focusProxy() is not None:
            continue
        if story_root is not None and (widget is story_root or story_root.isAncestorOf(widget)):
            continue
        found.append(widget)
    return found


def _assert_every_chrome_widget_is_named(window: GalleryWindow) -> None:
    focusables = _chrome_focusables(window)
    assert focusables
    unnamed = [f"{type(widget).__name__} {widget.objectName()!r}" for widget in focusables if not _name(widget)]
    assert unnamed == []


def test_every_focusable_chrome_widget_has_a_name_on_the_canvas_and_controls_tabs(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)

    _assert_every_chrome_widget_is_named(window)


def test_every_focusable_chrome_widget_has_a_name_on_the_docs_and_actions_tabs(qtbot, themes: BuiltinThemeProvider) -> None:
    stories = _registry()
    stories.get("Inputs/Button").variant("Wide", args={"text": "Wide"})
    window = _make(qtbot, themes, stories)
    _child(window, QTabWidget, "sbkPreviewTabs").setCurrentIndex(1)
    _child(window, QTabWidget, "sbkSideTabs").setCurrentIndex(1)
    qtbot.waitUntil(lambda: _child(window, QTableWidget, "sbkDocsControlsTable").isVisible(), timeout=5000)

    _assert_every_chrome_widget_is_named(window)
    assert any(isinstance(widget, QTableWidget) for widget in _chrome_focusables(window))
    assert any(isinstance(widget, QToolButton | QPushButton) and widget.text() == "Clear" for widget in _chrome_focusables(window))


def test_every_focusable_chrome_widget_has_a_name_when_a_story_fails(qtbot, themes: BuiltinThemeProvider) -> None:
    stories = StoryRegistry()

    @stories.story("Broken/Story")
    def broken(ctx: StoryContext) -> QWidget:
        raise RuntimeError("boom")

    window = _make(qtbot, themes, stories)

    assert window.findChild(ErrorPanel) is not None
    _assert_every_chrome_widget_is_named(window)


# Shortcuts and focus


def _story_input(window: GalleryWindow, kind: type[QWidget], name: str) -> QWidget:
    root = window.current_preview_widget()
    assert root is not None
    for widget in root.findChildren(kind):
        if widget.accessibleName() == name:
            return widget
    raise AssertionError(name)


def test_slash_types_into_a_line_edit_and_an_editable_combo_box_without_moving_focus(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    field = _story_input(window, QLineEdit, "Story field")
    editable = _story_input(window, QComboBox, "Story editable combo")
    assert isinstance(editable, QComboBox)

    _focus(qtbot, field)
    qtbot.keyClick(field, Qt.Key.Key_Slash)
    assert isinstance(field, QLineEdit)
    assert field.text() == "/"
    assert QApplication.focusWidget() is field

    _focus(qtbot, editable)
    qtbot.keyClick(editable, Qt.Key.Key_Slash)
    assert editable.currentText() == "/"
    assert _focused_name() == "Story editable combo"


def test_slash_does_not_fire_from_a_spin_box(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    spin = _story_input(window, QSpinBox, "Story spin")
    _focus(qtbot, spin)

    qtbot.keyClick(spin, Qt.Key.Key_Slash)

    assert _focused_name() == "Story spin"
    assert isinstance(spin, QSpinBox)
    assert spin.value() == 0


def test_slash_opens_the_search_from_the_tree(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _child(window, QTreeView, "sbkStoryTree"))

    _key(qtbot, Qt.Key.Key_Slash)

    qtbot.waitUntil(lambda: _focused_name() == "Search stories", timeout=5000)


def test_alt_down_still_opens_a_combo_boxs_popup(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    combo = _story_input(window, QComboBox, "Story combo")
    assert isinstance(combo, QComboBox)
    _focus(qtbot, combo)
    assert not combo.view().isVisible()

    qtbot.keyClick(combo, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)

    qtbot.waitUntil(combo.view().isVisible, timeout=5000)
    combo.hidePopup()


def test_the_theme_switch_popup_opens_with_alt_down_too(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    switch = _child(window, QComboBox, "sbkThemeSwitch")
    _focus(qtbot, switch)

    qtbot.keyClick(switch, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)

    qtbot.waitUntil(switch.view().isVisible, timeout=5000)
    assert window.current_story_id() == "Inputs/Button"
    switch.hidePopup()


def test_ctrl_alt_down_and_up_move_through_the_visible_stories(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _child(window, QTreeView, "sbkStoryTree"))
    ctrl_alt = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier

    _key(qtbot, Qt.Key.Key_Down, ctrl_alt)
    assert window.current_story_id() == "Display/Label"
    _key(qtbot, Qt.Key.Key_Down, ctrl_alt)
    assert window.current_story_id() == "Display/Plain"
    _key(qtbot, Qt.Key.Key_Down, ctrl_alt)
    assert window.current_story_id() == "Display/Plain"
    _key(qtbot, Qt.Key.Key_Up, ctrl_alt)
    assert window.current_story_id() == "Display/Label"
    _key(qtbot, Qt.Key.Key_Up, ctrl_alt)
    _key(qtbot, Qt.Key.Key_Up, ctrl_alt)
    assert window.current_story_id() == "Inputs/Button"


def test_ctrl_alt_down_expands_the_branch_of_the_story_it_opens(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    tree = _child(window, QTreeView, "sbkStoryTree")
    model = tree.model()
    display = next(model.index(row, 0) for row in range(model.rowCount()) if model.index(row, 0).data() == "Display")
    tree.collapse(display)
    assert not tree.isExpanded(display)
    _focus(qtbot, tree)

    _key(qtbot, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)

    assert window.current_story_id() == "Display/Label"
    assert tree.isExpanded(display)


def test_ctrl_alt_down_skips_the_stories_the_search_hides(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    search = _child(window, QLineEdit, "sbkStorySearch")
    qtbot.keyClicks(search, "plain")
    assert window.current_story_id() == "Inputs/Button"

    _key(qtbot, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)

    assert window.current_story_id() == "Display/Plain"


def test_ctrl_t_switches_to_the_next_theme_and_wraps(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    switch = _child(window, QComboBox, "sbkThemeSwitch")
    assert themes.current_theme() == "Light"

    _key(qtbot, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert themes.current_theme() == "Dark"
    assert switch.currentText() == "Dark"
    _key(qtbot, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert themes.current_theme() == "Light"
    assert switch.currentText() == "Light"


def test_focus_stays_on_the_editor_after_a_control_edit_rebuilds_the_preview(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    editor = next(widget for widget in _chrome_focusables(window) if widget.accessibleName() == "Text")
    _focus(qtbot, editor)
    before = window.current_preview_widget()

    qtbot.keyClicks(editor, "ab")

    assert window.current_preview_widget() is not before
    assert QApplication.focusWidget() is editor
    story_button = _story_input(window, QPushButton, "Story button")
    assert isinstance(story_button, QPushButton)
    assert story_button.text() == "ab"


def test_ctrl_t_with_focus_in_the_preview_leaves_focus_on_the_canvas(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _story_input(window, QPushButton, "Story button"))

    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)

    assert themes.current_theme() == "Dark"
    qtbot.waitUntil(lambda: QApplication.focusWidget() is _child(window, QScrollArea, "sbkPreviewScroll"), timeout=5000)
    assert _focused_name() == "Preview of Inputs/Button"


def test_selecting_a_story_with_focus_in_the_preview_leaves_focus_on_the_canvas(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    _focus(qtbot, _story_input(window, QLineEdit, "Story field"))

    _key(qtbot, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)

    assert window.current_story_id() == "Display/Label"
    assert QApplication.focusWidget() is _child(window, QScrollArea, "sbkPreviewScroll")


# Help dialog


def _shortcut_keys(window: GalleryWindow) -> set[str]:
    native = QKeySequence.SequenceFormat.NativeText
    keys = {shortcut.key().toString(native) for shortcut in window.findChildren(QShortcut)}
    keys.add(QKeySequence("F1").toString(native))
    return keys


def _dialog_rows(dialog: QDialog) -> list[tuple[str, str]]:
    table = dialog.findChild(QTableWidget, "sbkShortcutsTable")
    assert table is not None
    rows = []
    for row in range(table.rowCount()):
        keys, action = table.item(row, 0), table.item(row, 1)
        assert keys is not None
        assert action is not None
        rows.append((keys.text(), action.text()))
    return rows


def test_the_help_menu_has_a_plain_text_keyboard_shortcuts_entry(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)

    menus = [action for action in window.menuBar().actions() if action.menu() is not None]
    assert [action.text().replace("&", "") for action in menus] == ["Help"]
    help_menu = menus[0].menu()
    assert isinstance(help_menu, QMenu)
    entries = help_menu.actions()
    assert [entry.text().replace("&", "") for entry in entries] == ["Keyboard shortcuts"]
    assert entries[0].shortcut() == QKeySequence("F1")
    assert all(entry.icon().isNull() for entry in [*menus, *entries])


def _native(keys: str) -> str:
    """Return ``keys`` as the dialog shows them: native text, with the Command key symbol on macOS."""
    return QKeySequence(keys).toString(QKeySequence.SequenceFormat.NativeText)


def test_f1_opens_a_dialog_listing_every_shortcut_and_it_is_deleted_after_it_closes(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    assert window.findChild(QDialog, "sbkShortcutsDialog") is None

    _key(qtbot, Qt.Key.Key_F1)

    dialog = window.findChild(QDialog, "sbkShortcutsDialog")
    assert dialog is not None
    assert dialog.parent() is window
    assert dialog.isVisible()
    assert dialog.windowModality() == Qt.WindowModality.WindowModal
    rows = _dialog_rows(dialog)
    listed = {key for keys, _action in rows for key in keys.split(" or ")}
    assert _shortcut_keys(window) <= listed
    expected = ("Ctrl+Alt+Down", "Ctrl+Alt+Up", "Ctrl+T", "F6", "Shift+F6", "F1", "Ctrl+F")
    assert {keys for keys, _action in rows} >= {_native(keys) for keys in expected}
    assert all(action for _keys, action in rows)

    dialog.close()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.findChild(QDialog, "sbkShortcutsDialog") is None


def test_f1_twice_keeps_one_dialog(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)

    _key(qtbot, Qt.Key.Key_F1)
    dialog = window.findChild(QDialog, "sbkShortcutsDialog")
    assert dialog is not None
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is dialog, timeout=5000)
    _child(window, QTableWidget, "sbkShortcutsTable").setFocus()
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_F1)

    assert len(window.findChildren(QDialog, "sbkShortcutsDialog")) == 1
    dialog.close()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_shortcuts_dialog_table_and_the_window_rows_come_from_one_table(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)

    rows = window.shortcut_rows()

    window_keys = {keys for keys, _action in rows}
    assert {QKeySequence(shortcut.key()).toString(QKeySequence.SequenceFormat.NativeText) for shortcut in window.findChildren(QShortcut)} <= {
        key for keys in window_keys for key in keys.split(" or ")
    }


# Contrast


def _grab_ring(qtbot, factory) -> tuple[Counter[str], int]:
    """Tab onto a widget and return the colours of the pixels that changed, with the count of changed pixels."""
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    first = QLineEdit(host)
    target = factory(host)
    layout.addWidget(first)
    layout.addWidget(target)
    host.resize(300, 150)
    show_active(qtbot, host)
    _focus(qtbot, first)
    qtbot.wait(50)
    before = target.grab().toImage()
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: QApplication.focusWidget() is target, timeout=5000)
    qtbot.wait(50)
    after = target.grab().toImage()
    changed: Counter[str] = Counter()
    for x in range(after.width()):
        for y in range(after.height()):
            if after.pixelColor(x, y) != before.pixelColor(x, y):
                changed[after.pixelColor(x, y).name()] += 1
    return changed, sum(changed.values())


@pytest.mark.parametrize("theme", _THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("factory", [lambda parent: QLineEdit(parent), lambda parent: QPushButton("Button", parent)], ids=["line edit", "button"])
def test_the_rendered_focus_ring_reaches_3_to_1_against_window_and_base(qtbot, themes: BuiltinThemeProvider, theme, factory) -> None:
    themes.set_theme(theme.name)
    palette = QApplication.palette()
    changed, total = _grab_ring(qtbot, factory)

    assert total > 100
    ring, _count = changed.most_common(1)[0]
    assert contrast_ratio(ring, palette.color(QPalette.ColorRole.Window).name()) >= 3
    assert contrast_ratio(ring, palette.color(QPalette.ColorRole.Base).name()) >= 3


@pytest.mark.parametrize("theme", _THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("group", [QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive], ids=["active", "inactive"])
def test_selected_text_reaches_4_5_to_1_in_the_active_and_inactive_groups(theme, group: QPalette.ColorGroup) -> None:
    palette = theme.palette()

    text = palette.color(group, QPalette.ColorRole.HighlightedText).name()
    highlight = palette.color(group, QPalette.ColorRole.Highlight).name()

    assert contrast_ratio(text, highlight) >= 4.5


def _tint(source) -> str:
    return strongest_pixel(source).name()


@pytest.mark.parametrize("theme", _THEMES, ids=lambda theme: theme.name)
def test_every_chrome_icon_reaches_3_to_1_against_its_background(qtbot, themes: BuiltinThemeProvider, theme) -> None:
    themes.set_theme(theme.name)
    stories = _registry()
    window = _make(qtbot, themes, stories)
    palette = window.palette()
    window_color = palette.color(QPalette.ColorRole.Window).name()
    button_color = palette.color(QPalette.ColorRole.Button).name()
    base_color = palette.color(QPalette.ColorRole.Base).name()

    bound = list(window._icons._bound)
    assert len(bound) >= 6
    for binding in bound:
        background = base_color if not isinstance(binding.target, QToolButton | QPushButton) else button_color
        assert contrast_ratio(_tint(binding.target.icon()), background) >= 3, (binding.name, theme.name)

    status = ReloadStatus(window)
    for show in (status.show_success, functools.partial(status.show_failure, "because")):
        show()
        pixmap = status._icon.pixmap()
        assert contrast_ratio(_tint(pixmap), window_color) >= 3

    broken = StoryRegistry()

    @broken.story("Broken/Story")
    def broken_story(ctx: StoryContext) -> QWidget:
        raise ZeroDivisionError
    error_window = _make(qtbot, themes, broken)
    panel = error_window.findChild(ErrorPanel)
    assert panel is not None
    assert contrast_ratio(_tint(panel._icon.pixmap()), window_color) >= 3


# Large fonts


def _is_internal(widget: QWidget) -> bool:
    """Whether a widget is a part Qt builds inside another (a spin box's line edit, a line edit's clear button, a tab bar's scroll button)."""
    return widget.objectName().startswith("qt_") or isinstance(widget.parentWidget(), QLineEdit | QTabBar | QAbstractSpinBox | QComboBox)


def _chrome_widgets(window: GalleryWindow) -> list[QWidget]:
    canvas = window.findChild(Canvas)
    assert canvas is not None
    story_root = canvas.placed_widget()
    return [
        widget
        for widget in window.findChildren(QWidget)
        if not (story_root is not None and (widget is story_root or story_root.isAncestorOf(widget)))
    ]


def test_chrome_text_is_not_clipped_and_nothing_has_a_fixed_height_at_a_24_point_font(
    qtbot, qapp: QApplication, themes: BuiltinThemeProvider, restore_application_look: None
) -> None:
    font = QFont(qapp.font())
    font.setPointSize(24)
    qapp.setFont(font)
    stories = _registry()
    stories.get("Inputs/Button").variant("Wide", args={"text": "Wide"})
    window = _make(qtbot, themes, stories)
    window.resize(1500, 1000)

    for preview_tab, side_tab in [(0, 0), (1, 1)]:
        _child(window, QTabWidget, "sbkPreviewTabs").setCurrentIndex(preview_tab)
        _child(window, QTabWidget, "sbkSideTabs").setCurrentIndex(side_tab)
        qtbot.wait(100)
        for widget in _chrome_widgets(window):
            if not widget.isVisible():
                continue
            assert not (widget.minimumHeight() == widget.maximumHeight() and widget.maximumHeight() != _NO_LIMIT), (
                type(widget).__name__,
                widget.objectName(),
            )
            if isinstance(widget, QLabel):
                needed = widget.heightForWidth(widget.width()) if widget.hasHeightForWidth() else widget.sizeHint().height()
                assert needed <= widget.height(), (widget.text(), needed, widget.height())
            elif isinstance(widget, QComboBox | QToolButton | QPushButton | QLineEdit | QSpinBox) and not _is_internal(widget):
                assert widget.minimumSizeHint().height() <= widget.height(), (type(widget).__name__, widget.objectName())
        for bar in window.findChildren(QTabWidget):
            assert bar.tabBar().height() >= bar.tabBar().fontMetrics().height()


def test_the_status_bar_and_menu_bar_follow_the_font(qtbot, qapp: QApplication, themes: BuiltinThemeProvider, restore_application_look: None) -> None:
    font = QFont(qapp.font())
    font.setPointSize(24)
    qapp.setFont(font)
    window = _make(qtbot, themes)

    assert window.menuBar().height() >= window.menuBar().fontMetrics().height()
    status = window.findChild(QStatusBar)
    assert status is not None
    assert not (status.minimumHeight() == status.maximumHeight() and status.maximumHeight() != _NO_LIMIT)


def test_the_canvas_lists_its_shortcuts_from_the_table_that_creates_them(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make(qtbot, themes)
    canvas = window.findChild(Canvas)
    assert canvas is not None

    assert canvas.shortcut_help() == [
        (f"{_native('Ctrl++')} or {_native('Ctrl+=')}", "Zoom in"),
        (_native("Ctrl+-"), "Zoom out"),
        (_native("Ctrl+0"), "Reset zoom to 100%"),
    ]
    native = QKeySequence.SequenceFormat.NativeText
    created = {shortcut.key().toString(native) for shortcut in canvas.findChildren(QShortcut)}
    assert created == {key for keys, _description in canvas.shortcut_help() for key in keys.split(" or ")}
