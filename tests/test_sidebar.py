import pytest
from conftest import show_active
from icon_testing import assert_tinted, strongest_pixel
from PySide6.QtCore import QEvent, QSignalBlocker, QSortFilterProxyModel, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QSpinBox, QTreeView

from pyside6_storybook import FileControl, IntControl, LoadError, StoryRegistry, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.sidebar import StorySidebar, _StoryFilterModel
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemeProvider

pytestmark = pytest.mark.usefixtures("restore_window_activation")


def _registry(*ids: str) -> StoryRegistry:
    stories = StoryRegistry()
    for story_id in ids:
        stories.story(story_id)(lambda ctx: QLabel("x"))
    return stories


def _sidebar(qtbot, registry: StoryRegistry, *, load_errors: tuple[LoadError, ...] = ()) -> StorySidebar:
    sidebar = StorySidebar()
    qtbot.addWidget(sidebar)
    sidebar.set_registry(registry, load_errors=load_errors)
    return sidebar


def _tree(sidebar: StorySidebar) -> QTreeView:
    tree = sidebar.findChild(QTreeView)
    assert tree is not None
    return tree


def _search(sidebar: StorySidebar) -> QLineEdit:
    search = sidebar.findChild(QLineEdit, "sbkStorySearch")
    assert search is not None
    return search


def _rows(sidebar: StorySidebar) -> list[tuple[int, str]]:
    """The visible rows of the tree as ``(depth, label)``, in tree order."""
    model = _tree(sidebar).model()
    rows: list[tuple[int, str]] = []

    def walk(parent, depth: int) -> None:
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            rows.append((depth, str(index.data())))
            walk(index, depth + 1)

    walk(model.index(-1, -1), 0)
    return rows


def _expanded(sidebar: StorySidebar) -> dict[str, bool]:
    tree = _tree(sidebar)
    model = tree.model()
    found: dict[str, bool] = {}

    def walk(parent) -> None:
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if model.hasChildren(index):
                found[str(index.data())] = tree.isExpanded(index)
            walk(index)

    walk(model.index(-1, -1))
    return found


def _type(qtbot, sidebar: StorySidebar, text: str) -> None:
    search = _search(sidebar)
    search.clear()
    qtbot.keyClicks(search, text)


class _Recorder:
    def __init__(self, sidebar: StorySidebar) -> None:
        self.selected: list[str] = []
        self.errors = 0
        sidebar.storySelected.connect(self.selected.append)
        sidebar.loadErrorsSelected.connect(self._count)

    def _count(self) -> None:
        self.errors += 1


# Tree shape


def test_the_tree_has_one_branch_per_segment_and_keeps_registration_order(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("Zeta/One", "Alpha/Two", "Zeta/Three", "Alpha/Nested/Four", "Alpha/Nested/Five"))

    assert _rows(sidebar) == [
        (0, "Zeta"),
        (1, "One"),
        (1, "Three"),
        (0, "Alpha"),
        (1, "Two"),
        (1, "Nested"),
        (2, "Four"),
        (2, "Five"),
    ]
    assert sidebar.visible_story_ids() == ["Zeta/One", "Zeta/Three", "Alpha/Two", "Alpha/Nested/Four", "Alpha/Nested/Five"]
    assert all(_expanded(sidebar).values())


def test_a_one_story_component_below_the_top_level_shows_as_its_story(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("Forms/Sign-in Form/Default", "Forms/Other"))

    assert _rows(sidebar) == [(0, "Forms"), (1, "Sign-in Form"), (1, "Other")]
    assert sidebar.visible_story_ids() == ["Forms/Sign-in Form/Default", "Forms/Other"]
    recorder = _Recorder(sidebar)
    assert sidebar.select_story("Forms/Sign-in Form/Default")
    assert recorder.selected == ["Forms/Sign-in Form/Default"]


def test_a_top_level_branch_with_one_story_is_not_collapsed(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("Forms/Sign-in Form"))

    assert _rows(sidebar) == [(0, "Forms"), (1, "Sign-in Form")]


def test_a_component_with_two_stories_is_not_collapsed(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B/One", "A/B/Two"))

    assert _rows(sidebar) == [(0, "A"), (1, "B"), (2, "One"), (2, "Two")]


def test_a_story_that_is_also_a_branch_is_a_story_row_with_children(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B", "A/B/C", "A/D"))

    assert _rows(sidebar) == [(0, "A"), (1, "B"), (2, "C"), (1, "D")]
    assert sidebar.visible_story_ids() == ["A/B", "A/B/C", "A/D"]
    recorder = _Recorder(sidebar)
    assert sidebar.select_story("A/B")
    assert recorder.selected == ["A/B"]


def test_a_story_registered_after_its_children_is_still_the_branch_row(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B/C", "A/B/E", "A/B"))

    assert _rows(sidebar) == [(0, "A"), (1, "B"), (2, "C"), (2, "E")]
    assert sidebar.visible_story_ids() == ["A/B", "A/B/C", "A/B/E"]


def test_story_rows_carry_the_full_id_as_tooltip_and_accessible_description(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B", "A/C"))
    model = _tree(sidebar).model()
    story_row = model.index(0, 0, model.index(0, 0))

    assert story_row.data(Qt.ItemDataRole.ToolTipRole) == "A/B"
    assert story_row.data(Qt.ItemDataRole.AccessibleDescriptionRole) == "A/B"
    assert model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole) is None


def test_load_errors_are_the_last_top_level_row(qtbot) -> None:
    errors = (LoadError("a.py", "boom"), LoadError("b.py", "bang"))
    sidebar = _sidebar(qtbot, _registry("A/B", "A/C"), load_errors=errors)

    assert _rows(sidebar)[-1] == (0, "Load errors (2)")
    assert sidebar.load_errors_label() == "Load errors (2)"
    assert sidebar.visible_story_ids() == ["A/B", "A/C"]
    assert _sidebar(qtbot, _registry("A/B")).load_errors_label() is None


# Filtering


def test_the_filter_is_a_case_insensitive_substring_match_on_the_full_id(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("Inputs/Button", "Display/Label", "Display/Buttons Gallery"))

    _type(qtbot, sidebar, "BUTTON")
    assert sidebar.visible_story_ids() == ["Inputs/Button", "Display/Buttons Gallery"]
    _type(qtbot, sidebar, "display/lab")
    assert sidebar.visible_story_ids() == ["Display/Label"]


def test_branches_never_match_by_themselves(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("Inputs/Button", "Display/Label"))

    _type(qtbot, sidebar, "zzz")

    assert sidebar.visible_story_ids() == []
    assert _rows(sidebar) == []


def test_the_filter_keeps_ancestors_and_expands_them(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B/One", "A/B/Two", "A/C", "D/E"))
    index = _tree(sidebar).model().index(0, 0)
    _tree(sidebar).collapse(index)

    _type(qtbot, sidebar, "two")

    assert _rows(sidebar) == [(0, "A"), (1, "B"), (2, "Two")]
    assert _expanded(sidebar) == {"A": True, "B": True}


def test_the_expansion_is_restored_when_the_search_is_cleared(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B/One", "A/B/Two", "C/D", "C/E"))
    model = _tree(sidebar).model()
    _tree(sidebar).collapse(model.index(1, 0))
    assert _expanded(sidebar) == {"A": True, "B": True, "C": False}

    _type(qtbot, sidebar, "d")
    assert _expanded(sidebar)["C"] is True
    _search(sidebar).clear()

    assert _expanded(sidebar) == {"A": True, "B": True, "C": False}


def test_a_search_with_no_match_shows_the_empty_state_instead_of_the_tree(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B"))
    sidebar.show()

    _type(qtbot, sidebar, "xyz")

    label = sidebar.findChild(QLabel, "sbkStorySearchEmptyState")
    assert label is not None
    assert label.isVisible()
    assert label.text() == "No stories match 'xyz'."
    assert not _tree(sidebar).isVisible()
    _search(sidebar).clear()
    assert not label.isVisible()
    assert _tree(sidebar).isVisible()


def test_typing_double_in_the_examples_leaves_only_the_double_spin_box(qtbot, stories: StoryRegistry) -> None:
    examples = load_stories([EXAMPLES_MODULE]).registry
    sidebar = _sidebar(qtbot, examples)

    _type(qtbot, sidebar, "double")

    assert sidebar.visible_story_ids() == ["Inputs/Double Spin Box"]
    assert _rows(sidebar) == [(0, "Inputs"), (1, "Double Spin Box")]
    assert _expanded(sidebar) == {"Inputs": True}


def test_the_load_errors_row_is_hidden_while_searching(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B"), load_errors=(LoadError("a.py", "boom"),))

    _type(qtbot, sidebar, "b")
    assert (0, "Load errors (1)") not in _rows(sidebar)
    _search(sidebar).clear()
    assert (0, "Load errors (1)") in _rows(sidebar)


# Selection and signals


def test_select_story_emits_and_set_registry_does_not(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B", "A/C"))
    recorder = _Recorder(sidebar)

    assert sidebar.select_story("A/C")
    assert recorder.selected == ["A/C"]
    assert sidebar.selected_story_id() == "A/C"
    sidebar.set_registry(_registry("A/B", "A/C", "A/D"))

    assert recorder.selected == ["A/C"]
    assert sidebar.selected_story_id() == "A/C"
    assert _tree(sidebar).currentIndex().data() == "C"
    assert not sidebar.select_story("Nope/Nothing")
    assert recorder.selected == ["A/C"]


def test_story_ids_lists_every_story_in_tree_order_including_the_ones_the_filter_hides(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "B/One", "A/Two"))
    _search(sidebar).setText("Two")

    assert sidebar.visible_story_ids() == ["A/Two"]
    assert sidebar.story_ids() == ["A/One", "A/Two", "B/One"]


def test_set_registry_forgets_a_selection_that_no_longer_exists(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B", "A/C"))
    sidebar.select_story("A/C")
    recorder = _Recorder(sidebar)

    sidebar.set_registry(_registry("A/B"))

    assert sidebar.selected_story_id() is None
    assert recorder.selected == []


def test_set_registry_keeps_a_collapsed_branch_collapsed_and_expands_a_new_one(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two", "B/One", "B/Two"))
    _tree(sidebar).collapse(_tree(sidebar).model().index(0, 0))

    sidebar.set_registry(_registry("A/One", "A/Two", "B/One", "B/Two", "C/One", "C/Two"))

    assert _expanded(sidebar) == {"A": False, "B": True, "C": True}


@pytest.mark.filterwarnings("ignore:Function.*invalidateFilter:DeprecationWarning")
def test_the_filter_falls_back_to_invalidate_filter_without_end_filter_change(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(_model: QSortFilterProxyModel) -> None:
        raise AssertionError("beginFilterChange needs endFilterChange, which this Qt lacks")

    monkeypatch.setattr(_StoryFilterModel, "endFilterChange", None, raising=False)
    monkeypatch.setattr(_StoryFilterModel, "beginFilterChange", forbidden, raising=False)
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))

    _type(qtbot, sidebar, "lab")
    assert sidebar.visible_story_ids() == ["A/Label"]
    _search(sidebar).clear()

    assert sidebar.visible_story_ids() == ["A/Button", "A/Label"]


def test_a_story_with_the_id_load_errors_is_a_story_not_the_errors_row(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("load-errors", "Other/One"), load_errors=(LoadError("a.py", "boom"),))
    recorder = _Recorder(sidebar)

    assert sidebar.select_story("load-errors")

    assert sidebar.selected_story_id() == "load-errors"
    assert not sidebar.load_errors_selected()
    assert recorder.selected == ["load-errors"]
    assert recorder.errors == 0
    sidebar.select_load_errors()
    assert sidebar.load_errors_selected()
    assert sidebar.selected_story_id() is None


def test_a_story_with_the_id_load_errors_stays_selected_over_a_set_registry(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("load-errors"), load_errors=(LoadError("a.py", "boom"),))
    sidebar.select_story("load-errors")

    sidebar.set_registry(_registry("load-errors", "B/One"), load_errors=(LoadError("a.py", "boom"),))

    assert sidebar.selected_story_id() == "load-errors"
    assert not sidebar.load_errors_selected()


def test_select_first_chooses_from_the_whole_tree_when_the_search_matches_no_new_story(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    sidebar.select_story("A/Label")
    _type(qtbot, sidebar, "label")
    recorder = _Recorder(sidebar)

    sidebar.set_registry(_registry("X/One", "X/Two"))
    assert sidebar.selected_story_id() is None
    assert sidebar.visible_story_ids() == []
    assert sidebar.select_first()

    assert sidebar.selected_story_id() == "X/One"
    assert recorder.selected == ["X/One"]
    assert _search(sidebar).text() == ""
    assert sidebar.visible_story_ids() == ["X/One", "X/Two"]


def test_a_filter_that_keeps_the_selected_story_leaves_it_selected(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    sidebar.select_story("A/Label")
    recorder = _Recorder(sidebar)

    _type(qtbot, sidebar, "lab")

    assert recorder.selected == []
    assert _tree(sidebar).currentIndex().data() == "Label"


def test_a_filter_that_hides_the_selected_story_emits_nothing_and_shows_it_selected_again(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label", "A/Slider"))
    sidebar.select_story("A/Label")
    recorder = _Recorder(sidebar)

    _type(qtbot, sidebar, "slid")
    assert recorder.selected == []
    assert sidebar.selected_story_id() == "A/Label"
    _type(qtbot, sidebar, "b")
    assert recorder.selected == []
    _search(sidebar).clear()

    assert recorder.selected == []
    assert _tree(sidebar).currentIndex().data() == "Label"


def test_select_story_clears_a_search_that_hides_it(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    _type(qtbot, sidebar, "button")
    recorder = _Recorder(sidebar)

    assert sidebar.select_story("A/Label")

    assert _search(sidebar).text() == ""
    assert recorder.selected == ["A/Label"]
    assert sidebar.visible_story_ids() == ["A/Button", "A/Label"]
    assert _tree(sidebar).currentIndex().data() == "Label"


def test_restoring_the_selection_after_a_search_does_not_expand_a_collapsed_branch(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two", "B/One", "B/Two"))
    sidebar.select_story("A/One")
    _tree(sidebar).collapse(_tree(sidebar).model().index(0, 0))
    recorder = _Recorder(sidebar)

    _type(qtbot, sidebar, "One")
    _search(sidebar).clear()

    assert _expanded(sidebar) == {"A": False, "B": True}
    assert sidebar.selected_story_id() == "A/One"
    assert recorder.selected == []


def test_set_registry_does_not_expand_a_collapsed_branch_of_the_selected_story(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two", "B/One", "B/Two"))
    sidebar.select_story("A/One")
    _tree(sidebar).collapse(_tree(sidebar).model().index(0, 0))

    sidebar.set_registry(_registry("A/One", "A/Two", "B/One", "B/Two"))

    assert _expanded(sidebar) == {"A": False, "B": True}
    assert sidebar.selected_story_id() == "A/One"


def test_select_story_expands_a_collapsed_branch(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two"))
    _tree(sidebar).collapse(_tree(sidebar).model().index(0, 0))

    sidebar.select_story("A/Two")

    assert _expanded(sidebar) == {"A": True}


def test_user_navigation_opens_the_story_at_once(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two"), load_errors=(LoadError("a.py", "boom"),))
    sidebar.show()
    recorder = _Recorder(sidebar)
    tree = _tree(sidebar)
    model = tree.model()

    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualRect(model.index(1, 0, model.index(0, 0))).center())
    assert recorder.selected == ["A/Two"]
    tree.setCurrentIndex(model.index(1, 0))
    assert recorder.errors == 1
    assert sidebar.load_errors_selected()
    tree.setCurrentIndex(model.index(0, 0))
    assert recorder.selected == ["A/Two"]
    assert recorder.errors == 1


# Keyboard


def test_down_from_the_search_field_selects_the_first_visible_story_and_enter_opens_it(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label", "B/Label"))
    show_active(qtbot, sidebar)
    recorder = _Recorder(sidebar)
    search = _search(sidebar)
    search.setFocus()
    qtbot.keyClicks(search, "label")
    assert recorder.selected == []

    qtbot.keyClick(search, Qt.Key.Key_Down)

    assert recorder.selected == ["A/Label"]
    assert _tree(sidebar).hasFocus()
    search.setFocus()
    qtbot.keyClick(search, Qt.Key.Key_Return)
    assert recorder.selected == ["A/Label", "A/Label"]


def test_enter_in_the_search_field_opens_the_first_visible_story(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    show_active(qtbot, sidebar)
    recorder = _Recorder(sidebar)
    search = _search(sidebar)
    search.setFocus()
    qtbot.keyClicks(search, "lab")

    qtbot.keyClick(search, Qt.Key.Key_Return)

    assert recorder.selected == ["A/Label"]


def test_escape_clears_the_search_and_then_moves_focus_to_the_tree(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    show_active(qtbot, sidebar)
    search = _search(sidebar)
    search.setFocus()
    qtbot.keyClicks(search, "lab")

    qtbot.keyClick(search, Qt.Key.Key_Escape)
    assert search.text() == ""
    assert search.hasFocus()
    qtbot.keyClick(search, Qt.Key.Key_Escape)

    assert _tree(sidebar).hasFocus()


def test_escape_in_the_tree_clears_the_search(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/Button", "A/Label"))
    show_active(qtbot, sidebar)
    _type(qtbot, sidebar, "lab")
    _tree(sidebar).setFocus()

    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Escape)

    assert _search(sidebar).text() == ""


def test_up_and_down_in_the_tree_move_between_visible_rows_and_open_stories(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two", "B/Three"))
    show_active(qtbot, sidebar)
    sidebar.select_story("A/One")
    recorder = _Recorder(sidebar)
    _tree(sidebar).setFocus()

    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Down)
    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Down)
    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Down)
    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Up)

    assert recorder.selected == ["A/Two", "B/Three"]


def test_enter_in_the_tree_opens_the_current_story(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two"))
    show_active(qtbot, sidebar)
    sidebar.select_story("A/Two")
    recorder = _Recorder(sidebar)
    _tree(sidebar).setFocus()

    qtbot.keyClick(_tree(sidebar), Qt.Key.Key_Return)

    assert recorder.selected == ["A/Two"]



def test_enter_opens_the_story_without_the_trees_activated_signal(qtbot) -> None:
    # On macOS Qt's item views start editing on Return and never emit activated; blocking the tree's signals does the same here.
    sidebar = _sidebar(qtbot, _registry("A/One", "A/Two"))
    show_active(qtbot, sidebar)
    sidebar.select_story("A/Two")
    recorder = _Recorder(sidebar)
    tree = _tree(sidebar)
    tree.setFocus()

    with QSignalBlocker(tree):
        qtbot.keyClick(tree, Qt.Key.Key_Return)
        qtbot.keyClick(tree, Qt.Key.Key_Enter)

    assert recorder.selected == ["A/Two", "A/Two"]

# The window's shortcuts


def _window(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> tuple[GalleryWindow, StorySidebar]:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    show_active(qtbot, window)
    sidebar = window.findChild(StorySidebar)
    assert sidebar is not None
    return window, sidebar


@pytest.mark.parametrize(
    ("key", "modifier"),
    [(Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier), (Qt.Key.Key_Slash, Qt.KeyboardModifier.NoModifier)],
)
def test_ctrl_f_and_slash_focus_the_search_from_the_tree(
    qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider, key: Qt.Key, modifier: Qt.KeyboardModifier
) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    _search(sidebar).setText("lab")
    _search(sidebar).deselect()
    _tree(sidebar).setFocus()
    qtbot.waitUntil(_tree(sidebar).hasFocus, timeout=5000)

    qtbot.keyClick(window, key, modifier)

    qtbot.waitUntil(_search(sidebar).hasFocus, timeout=5000)
    assert _search(sidebar).selectedText() == "lab"
    assert _search(sidebar).text() == "lab"


def test_slash_typed_into_a_line_edit_stays_there(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    edit = QLineEdit(window)
    edit.show()
    edit.setFocus()
    qtbot.waitUntil(edit.hasFocus, timeout=5000)

    qtbot.keyClick(edit, Qt.Key.Key_Slash)

    assert edit.text() == "/"
    assert edit.hasFocus()
    assert not _search(sidebar).hasFocus()


def test_slash_from_a_spin_box_neither_fires_nor_moves_focus(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    spin = QSpinBox(window)
    spin.show()
    spin.setFocus()
    qtbot.waitUntil(spin.hasFocus, timeout=5000)

    qtbot.keyClick(spin, Qt.Key.Key_Slash)

    assert spin.hasFocus()
    assert not _search(sidebar).hasFocus()
    assert spin.value() == 0


def test_slash_from_a_non_editable_combo_box_does_nothing(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    combo = window.findChild(QComboBox, "sbkThemeSwitch")
    assert combo is not None
    combo.setFocus()
    qtbot.waitUntil(combo.hasFocus, timeout=5000)

    qtbot.keyClick(combo, Qt.Key.Key_Slash)

    assert combo.hasFocus()
    assert not _search(sidebar).hasFocus()


# The window


def test_typing_in_the_search_never_changes_the_previewed_story(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    window.select_story("Display/Label")
    preview = window.current_preview_widget()
    search = _search(sidebar)
    search.setFocus()

    qtbot.keyClicks(search, "button")
    assert window.current_story_id() == "Display/Label"
    assert window.current_preview_widget() is preview
    search.clear()

    assert window.current_story_id() == "Display/Label"
    assert window.current_preview_widget() is preview


def test_window_select_story_opens_the_story_and_reports_unknown_ids(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    _type(qtbot, sidebar, "button")

    assert window.select_story("Display/Plain")
    assert window.current_story_id() == "Display/Plain"
    assert _search(sidebar).text() == ""
    assert not window.select_story("Nope")
    assert window.current_story_id() == "Display/Plain"


def test_window_set_registry_keeps_the_story_and_its_values_and_renders_once(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, _ = _window(qtbot, registry, themes)
    editor = next(e for e in window.findChildren(QLineEdit) if e.objectName() != "sbkStorySearch" and e.isVisibleTo(window))
    editor.selectAll()
    qtbot.keyClicks(editor, "Save")
    replacement = StoryRegistry()
    replacement.register(registry.get("Inputs/Button"))
    replacement.story("Display/New")(lambda ctx: QLabel("new"))

    window.set_registry(replacement)

    assert window.current_story_id() == "Inputs/Button"
    preview = window.current_preview_widget()
    assert preview is not None
    assert preview.property("text") == "Save"


def test_window_set_registry_falls_back_to_defaults_when_a_value_is_rejected(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, _ = _window(qtbot, registry, themes)
    window.select_story("Display/Label")
    narrower = StoryRegistry()
    narrower.story("Display/Label", controls=[IntControl("size", 3, 1, 5)])(lambda ctx: QLabel(f"size {ctx.args['size']}"))

    window.set_registry(narrower)

    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "size 3"


def test_window_set_registry_selects_the_story_at_the_same_row_when_the_story_is_gone(
    qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider
) -> None:
    window, _ = _window(qtbot, registry, themes)
    window.select_story("Display/Label")

    window.set_registry(_registry("X/One", "X/Two"))

    assert window.current_story_id() == "X/Two"
    window.set_registry(StoryRegistry(), load_errors=(LoadError("a.py", "boom"),))
    assert window.current_story_id() is None
    heading = window.findChild(QLabel, "sbkPreviewHeading")
    assert heading is not None
    assert heading.text() == "Load errors"


def _story_with_controls(registry: StoryRegistry, story_id: str, *names: str) -> None:
    registry.story(story_id, controls=[IntControl(name, 1, 0, 100) for name in names])(lambda ctx: QLabel(str(sorted(ctx.args.items()))))


def test_window_set_registry_starts_from_the_new_defaults_and_overlays_the_previous_values(qtbot, themes: BuiltinThemeProvider) -> None:
    old = StoryRegistry()
    _story_with_controls(old, "T/Label/Default", "a", "gone")
    old.get("T/Label/Default").variant("Loud", args={"a": 3})
    window, _ = _window(qtbot, old, themes)
    window.select_story("T/Label/Loud")
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    old_panel = window.findChild(ControlsPanel)
    assert old_panel is not None
    old_panel.findChildren(QSpinBox)[0].setValue(5)
    new = StoryRegistry()
    _story_with_controls(new, "T/Label/Default", "a", "b")
    new.get("T/Label/Default").variant("Loud", args={"a": 3, "b": 9})

    window.set_registry(new)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert window.current_story_id() == "T/Label/Loud"
    panel = window.findChild(ControlsPanel)
    assert panel is not None
    assert panel.values() == {"a": 5, "b": 9}
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == str([("a", 5), ("b", 9)])


def test_window_set_registry_builds_one_controls_panel_even_when_a_value_is_rejected(qtbot, themes: BuiltinThemeProvider) -> None:
    old = StoryRegistry()
    _story_with_controls(old, "T/One", "a", "b")
    window, _ = _window(qtbot, old, themes)
    old_panel = window.findChild(ControlsPanel)
    assert old_panel is not None
    spin_boxes = old_panel.findChildren(QSpinBox)
    spin_boxes[0].setValue(50)
    spin_boxes[1].setValue(60)
    new = StoryRegistry()
    new.story("T/One", controls=[IntControl("a", 1, 0, 10), IntControl("b", 1, 0, 100)])(lambda ctx: QLabel("x"))

    window.set_registry(new)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    panel = window.findChild(ControlsPanel)
    assert panel is not None
    assert panel.values() == {"a": 1, "b": 60}
    assert len(window.findChildren(ControlsPanel)) == 1


# Appearance and accessibility


def test_the_search_field_has_a_clear_button_and_accessible_names(qtbot) -> None:
    sidebar = _sidebar(qtbot, _registry("A/B"))

    assert _search(sidebar).isClearButtonEnabled()
    assert _search(sidebar).accessibleName() == "Search stories"
    assert _tree(sidebar).accessibleName() == "Stories"
    assert sidebar.accessibleName() == "Story list"


def test_the_search_icon_is_tinted_from_the_palette_and_follows_a_theme_switch(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, sidebar = _window(qtbot, registry, themes)
    (action,) = [a for a in _search(sidebar).actions() if not a.icon().isNull()]

    def tinted_like_placeholder() -> None:
        expected = QApplication.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.PlaceholderText)
        assert_tinted(strongest_pixel(action.icon()), expected.name())

    tinted_like_placeholder()
    before = strongest_pixel(action.icon()).name()
    window.set_theme("Dark")
    qtbot.waitUntil(lambda: strongest_pixel(action.icon()).name() != before, timeout=5000)
    tinted_like_placeholder()


# Light and Dark only: System is Qt's own palette, whose selection contrast is 3.69:1 offscreen and not ours to guarantee.
@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_the_inactive_selection_keeps_a_readable_contrast(theme: str, qapp: QApplication, themes: BuiltinThemeProvider) -> None:
    themes.set_theme(theme)
    palette = QApplication.palette()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        text = palette.color(group, QPalette.ColorRole.HighlightedText)
        background = palette.color(group, QPalette.ColorRole.Highlight)
        assert contrast_ratio(text.name(), background.name()) >= 4.5, (theme, group)



def test_window_set_registry_keeps_a_cleared_file_control_empty(qtbot, themes: BuiltinThemeProvider) -> None:
    def build() -> StoryRegistry:
        registry = StoryRegistry()
        registry.story("Files/Picker", controls=[FileControl("path", "default.png")])(lambda ctx: QLabel(str(ctx.args["path"])))
        return registry

    window = GalleryWindow(build(), themes)
    qtbot.addWidget(window)
    window.select_story("Files/Picker")
    panel = window.findChild(ControlsPanel)
    assert panel is not None
    field = panel.findChild(QLineEdit)
    assert field is not None
    field.clear()
    field.editingFinished.emit()
    assert panel.values() == {"path": None}

    window.set_registry(build())

    new_panel = [found for found in window.findChildren(ControlsPanel) if found.isVisibleTo(window)][-1]
    assert new_panel.values() == {"path": None}
