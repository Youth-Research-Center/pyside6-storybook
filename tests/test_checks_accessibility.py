"""``check_accessible_names`` and ``check_keyboard_focus`` on hand-built widgets."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

import pyside6_storybook
from pyside6_storybook.checks import CheckIssue, check_accessible_names, check_keyboard_focus


def _shown(qtbot, *children: QWidget) -> QWidget:
    root = QWidget()
    layout = QVBoxLayout(root)
    for child in children:
        layout.addWidget(child)
    qtbot.addWidget(root)
    root.show()
    qtbot.waitUntil(root.isVisible, timeout=5000)
    return root


def test_an_icon_only_tool_button_fails_name_and_setting_an_accessible_name_fixes_it(qtbot) -> None:
    button = QToolButton()
    button.setToolTip("Close")
    root = _shown(qtbot, button)

    issues = check_accessible_names(root)

    assert issues == [
        CheckIssue(
            rule="name",
            widget_class="QToolButton",
            object_name="",
            path="QWidget/QToolButton[0]",
            message="has no accessible name; call setAccessibleName()",
        )
    ]
    button.setAccessibleName("Close")
    assert check_accessible_names(root) == []


def test_a_button_with_text_has_a_name_and_mnemonics_do_not_count_against_it(qtbot) -> None:
    root = _shown(qtbot, QPushButton("&Save"))

    assert check_accessible_names(root) == []


def test_a_no_focus_push_button_fails_focus(qtbot) -> None:
    button = QPushButton("Skip me")
    button.setObjectName("skip")
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    root = _shown(qtbot, button)

    issues = check_keyboard_focus(root)

    assert [(issue.rule, issue.widget_class, issue.object_name, issue.path) for issue in issues] == [
        ("focus", "QPushButton", "skip", "QWidget/QPushButton[0]")
    ]
    assert "TabFocus" in issues[0].message
    assert "skip" in str(issues[0])
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    assert check_keyboard_focus(root) == []


def test_a_labelled_line_edit_with_a_buddy_passes_and_an_unlabelled_one_fails(qtbot) -> None:
    label = QLabel("&Name")
    edit = QLineEdit()
    label.setBuddy(edit)
    root = _shown(qtbot, label, edit)
    assert check_accessible_names(root) == []

    other = QLineEdit()
    other.setParent(root)
    other.show()

    assert [issue.path for issue in check_accessible_names(root)] == ["QWidget/QLineEdit[1]"]


def test_the_internals_of_spin_boxes_and_combo_boxes_are_not_reported(qtbot) -> None:
    spin, double, combo, editable = QSpinBox(), QDoubleSpinBox(), QComboBox(), QComboBox()
    editable.setEditable(True)
    for box in (spin, double):
        box.setAccessibleName("Number")
    for box in (combo, editable):
        box.addItems(["a", "b"])
        box.setAccessibleName("Choice")
    root = _shown(qtbot, spin, double, combo, editable)

    assert check_accessible_names(root) == []
    assert check_keyboard_focus(root) == []
    assert root.findChildren(QLineEdit)


def test_unnamed_spin_boxes_are_reported_once_each(qtbot) -> None:
    root = _shown(qtbot, QSpinBox(), QDoubleSpinBox())

    assert [issue.widget_class for issue in check_accessible_names(root)] == ["QSpinBox", "QDoubleSpinBox"]


def test_an_unlabelled_combo_box_fails_although_its_current_text_is_not_empty(qtbot) -> None:
    combo = QComboBox()
    combo.addItems(["Apple", "Banana"])
    root = _shown(qtbot, combo)

    issues = check_accessible_names(root)

    assert [issue.widget_class for issue in issues] == ["QComboBox"]
    assert "buddy label" in issues[0].message
    combo.setAccessibleName("Fruit")
    assert check_accessible_names(root) == []


def test_a_combo_box_with_a_buddy_label_passes(qtbot) -> None:
    combo = QComboBox()
    combo.addItems(["Apple"])
    label = QLabel("&Fruit")
    label.setBuddy(combo)
    root = _shown(qtbot, label, combo)

    assert check_accessible_names(root) == []


def test_item_view_headers_viewport_scroll_bars_and_corner_button_are_not_reported(qtbot) -> None:
    table = QTableWidget(40, 40)
    table.setAccessibleName("Table")
    table.setFixedSize(200, 150)
    tree = QTreeWidget()
    tree.setAccessibleName("Tree")
    root = _shown(qtbot, table, tree)

    assert check_accessible_names(root) == []
    assert check_keyboard_focus(root) == []
    assert table.horizontalScrollBar().isVisibleTo(root)


def test_an_unnamed_table_fails_once_without_its_internals(qtbot) -> None:
    root = _shown(qtbot, QTableWidget(3, 3))

    assert [issue.widget_class for issue in check_accessible_names(root)] == ["QTableWidget"]


def test_a_line_edit_clear_button_is_not_reported(qtbot) -> None:
    edit = QLineEdit("x")
    edit.setAccessibleName("Text")
    edit.setClearButtonEnabled(True)
    root = _shown(qtbot, edit)

    assert check_accessible_names(root) == []
    assert check_keyboard_focus(root) == []


def test_a_tab_widget_is_checked_through_its_tab_texts(qtbot) -> None:
    tabs = QTabWidget()
    tabs.addTab(QLabel("one"), "One")
    tabs.addTab(QLabel("two"), "")
    root = _shown(qtbot, tabs)

    issues = check_accessible_names(root)

    assert [(issue.widget_class, issue.message) for issue in issues] == [("QTabWidget", "tab 1 has no text; call setTabText()")]
    assert check_keyboard_focus(root) == []
    tabs.setTabText(1, "&Two")
    assert check_accessible_names(root) == []


def test_a_tab_widgets_tab_bar_is_not_reported_and_a_hidden_page_is_not_checked(qtbot) -> None:
    tabs = QTabWidget()
    tabs.addTab(QLabel("one"), "One")
    hidden = QToolButton()
    tabs.addTab(hidden, "Two")
    root = _shown(qtbot, tabs)

    assert check_accessible_names(root) == []


def test_a_scroll_area_is_a_container_and_its_content_is_checked(qtbot) -> None:
    area = QScrollArea()
    content = QWidget()
    inner = QToolButton(content)
    QVBoxLayout(content).addWidget(inner)
    area.setWidget(content)
    root = _shown(qtbot, area)

    issues = check_accessible_names(root)

    assert [issue.widget_class for issue in issues] == ["QToolButton"]
    assert check_keyboard_focus(root) == []


def test_hidden_and_disabled_widgets_are_not_checked(qtbot) -> None:
    hidden, disabled = QToolButton(), QToolButton()
    disabled.setEnabled(False)
    root = _shown(qtbot, hidden, disabled)
    hidden.hide()

    assert check_accessible_names(root) == []


def test_the_path_counts_siblings_of_the_same_class_inside_groups(qtbot) -> None:
    group = QGroupBox()
    layout = QVBoxLayout(group)
    layout.addWidget(QPushButton("ok"))
    layout.addWidget(QToolButton())
    layout.addWidget(QToolButton())
    root = _shown(qtbot, group)

    assert [issue.path for issue in check_accessible_names(root)] == ["QWidget/QGroupBox[0]/QToolButton[0]", "QWidget/QGroupBox[0]/QToolButton[1]"]


def test_the_checked_widget_itself_is_checked(qtbot) -> None:
    button = QToolButton()
    qtbot.addWidget(button)
    button.show()

    assert [issue.path for issue in check_accessible_names(button)] == ["QToolButton"]


@pytest.mark.parametrize("name", ["check_accessible_names", "check_keyboard_focus"])
def test_the_checks_are_public_in_the_checks_package_and_not_in_the_root(name: str) -> None:
    assert not hasattr(pyside6_storybook, name)
    assert "CheckIssue" not in pyside6_storybook.__all__
