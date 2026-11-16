"""The wheel filter: an editor in a scrolling pane only reacts to the wheel while it has keyboard focus."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class _WheelFilter(QObject):
    """Ignores wheel events for a widget that does not have focus, so the pane under the pointer scrolls instead."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Swallow a wheel event for an unfocused widget, leaving it unaccepted so Qt passes it to the parent."""
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QWidget) and not watched.hasFocus():
            event.ignore()
            return True
        return False


def guard_wheel(widget: QWidget) -> None:
    """Make ``widget`` take focus by click or Tab only and ignore the wheel until it has focus.

    Args:
        widget: A spin box, slider or combo box. It owns the filter, which is deleted with it.
    """
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(_WheelFilter(widget))


__all__ = ["guard_wheel"]
