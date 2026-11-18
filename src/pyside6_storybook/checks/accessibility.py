"""``check_accessible_names`` and ``check_keyboard_focus``: what a screen reader and the Tab key see of a widget tree."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QScrollBar,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from pyside6_storybook.checks.check_issue import CheckIssue
from pyside6_storybook.checks.rules import RULE_FOCUS, RULE_NAME

_CONTROL_TYPES = (
    QAbstractButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QAbstractSpinBox,
    QComboBox,
    QAbstractSlider,
    QAbstractItemView,
    QTabBar,
)
"""The widgets that are controls whatever their focus policy."""

_INTERNAL_PARENTS = (QAbstractSpinBox, QComboBox, QLineEdit, QTabBar)
"""Widgets whose children are their own internals, which they name and focus for themselves."""


def check_accessible_names(widget: QWidget) -> list[CheckIssue]:
    """Find the controls in ``widget`` that have no accessible name, which a screen reader cannot announce.

    The widget itself and its visible, enabled descendants are checked when they are buttons, line and text edits, spin boxes, combo
    boxes, sliders, item views or tab bars, or take focus with the Tab key. A name is what a screen reader reads: the widget's text, the
    text of a buddy label, or ``setAccessibleName``; a tooltip is not a name. A combo box needs ``setAccessibleName`` or a buddy label,
    because its current text does not count. The tabs of a tab widget are checked through their texts. The internals of composite
    widgets (the line edit of a spin box, the headers and scroll bars of an item view, the tab bar of a tab widget) are not checked.

    Args:
        widget: The widget to check, with everything in it.

    Returns:
        The issues, in the order the widgets are found; empty when every control has a name.
    """
    issues: list[CheckIssue] = []
    for control in _controls(widget):
        if not _accessible_name(control):
            hint = "give it a buddy label or call setAccessibleName()" if isinstance(control, QComboBox) else "call setAccessibleName()"
            issues.append(_issue(RULE_NAME, widget, control, f"has no accessible name; {hint}"))
    for tabs in _tab_widgets(widget):
        bar = tabs.tabBar()
        for index in range(tabs.count()):
            if bar.isTabVisible(index) and bar.isTabEnabled(index) and not (bar.accessibleTabName(index) or _plain(tabs.tabText(index))):
                issues.append(_issue(RULE_NAME, widget, tabs, f"tab {index} has no text; call setTabText()"))
    return issues


def check_keyboard_focus(widget: QWidget) -> list[CheckIssue]:
    """Find the controls in ``widget`` that the Tab key cannot reach.

    The same widgets are checked as in ``check_accessible_names``; each must have a focus policy that includes ``Qt.FocusPolicy.TabFocus``.

    Args:
        widget: The widget to check, with everything in it.

    Returns:
        The issues, in the order the widgets are found; empty when every control takes focus with Tab.
    """
    return [
        _issue(RULE_FOCUS, widget, control, "cannot be reached with the Tab key; its focus policy lacks TabFocus (use StrongFocus or TabFocus)")
        for control in _controls(widget)
        if not control.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]


def _controls(root: QWidget) -> Iterator[QWidget]:
    """Yield the root and its descendants that are checked: visible to the root, enabled, a control or focusable by Tab, not internal."""
    for candidate in [root, *root.findChildren(QWidget)]:
        if _is_checked(root, candidate):
            yield candidate


def _tab_widgets(root: QWidget) -> Iterator[QTabWidget]:
    for candidate in [root, *root.findChildren(QTabWidget)]:
        if isinstance(candidate, QTabWidget) and candidate.isVisibleTo(root) and candidate.isEnabled() and candidate.window() is root.window():
            yield candidate


def _is_checked(root: QWidget, widget: QWidget) -> bool:
    if widget.window() is not root.window() or not widget.isVisibleTo(root) or not widget.isEnabled():
        return False
    if not (isinstance(widget, _CONTROL_TYPES) or widget.focusPolicy() & Qt.FocusPolicy.TabFocus):
        return False
    if isinstance(widget, (QScrollBar, QTabWidget, QScrollArea)):
        return False
    return not _is_internal(widget)


def _is_internal(widget: QWidget) -> bool:
    """Whether ``widget`` is an internal of a composite that handles it itself, wherever the composite is in the tree."""
    parent = widget.parentWidget()
    if isinstance(widget, QTabBar) and isinstance(parent, QTabWidget) and parent.tabBar() is widget:
        return True
    while parent is not None:
        if isinstance(parent, _INTERNAL_PARENTS):
            return True
        if isinstance(parent, QAbstractScrollArea) and not _in_viewport(parent, widget):
            return True
        proxy = parent.focusProxy()
        while proxy is not None and proxy is not parent:
            if proxy is widget:
                return True
            proxy = proxy.focusProxy()
        parent = parent.parentWidget()
    return False


def _in_viewport(area: QAbstractScrollArea, widget: QWidget) -> bool:
    """Whether ``widget`` is something shown in the viewport (an index widget or an editor); the viewport itself is not."""
    return area.viewport().isAncestorOf(widget)


def _accessible_name(widget: QWidget) -> str:
    if isinstance(widget, QComboBox):
        return widget.accessibleName().strip() or _buddy_label(widget)
    interface = QAccessible.queryAccessibleInterface(widget)
    return interface.text(QAccessible.Text.Name).strip() if interface is not None else ""


def _buddy_label(widget: QWidget) -> str:
    for label in widget.window().findChildren(QLabel):
        if label.buddy() is widget:
            interface = QAccessible.queryAccessibleInterface(label)
            name = interface.text(QAccessible.Text.Name).strip() if interface is not None else ""
            if name:
                return name
    return ""


def _plain(text: str) -> str:
    """Return ``text`` without mnemonics: ``&Save`` is ``Save``, ``&&`` is a literal ``&``."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&").strip()


def _issue(rule: str, root: QWidget, widget: QWidget, message: str) -> CheckIssue:
    return CheckIssue(
        rule=rule,
        widget_class=type(widget).__name__,
        object_name=widget.objectName(),
        path=_path(root, widget),
        message=message,
    )


def _path(root: QWidget, widget: QWidget) -> str:
    """Return the class names from ``root`` to ``widget``, each below the root with its index among the siblings of the same class."""
    parts: list[str] = []
    current = widget
    while current is not root:
        parent = current.parentWidget()
        if parent is None:
            break
        siblings = [child for child in parent.children() if isinstance(child, QWidget) and type(child).__name__ == type(current).__name__]
        parts.append(f"{type(current).__name__}[{siblings.index(current)}]")
        current = parent
    parts.append(type(root).__name__)
    return "/".join(reversed(parts))


__all__ = ["check_accessible_names", "check_keyboard_focus"]
