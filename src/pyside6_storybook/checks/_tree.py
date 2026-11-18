"""Walking a widget tree, shared by the checks (internal)."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractScrollArea, QAbstractSpinBox, QComboBox, QLineEdit, QTabBar, QTabWidget, QWidget

from pyside6_storybook.checks.check_issue import CheckIssue

_INTERNAL_PARENTS = (QAbstractSpinBox, QComboBox, QLineEdit, QTabBar)
"""Widgets whose children are their own internals, which they name, focus and paint for themselves."""


def is_internal(widget: QWidget) -> bool:
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


def make_issue(rule: str, root: QWidget, widget: QWidget, message: str) -> CheckIssue:
    return CheckIssue(
        rule=rule,
        widget_class=type(widget).__name__,
        object_name=widget.objectName(),
        path=widget_path(root, widget),
        message=message,
    )


def widget_path(root: QWidget, widget: QWidget) -> str:
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


__all__ = ["is_internal", "make_issue", "widget_path"]
