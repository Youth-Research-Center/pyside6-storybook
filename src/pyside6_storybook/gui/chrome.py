"""Marking the gallery's own widgets so an application style sheet can address them (and only them)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

CHROME_PROPERTY = "sbkChrome"


def mark_chrome(widget: QWidget, name: str = "", *, chrome: bool = True) -> None:
    """Give a widget of the gallery its object name and, unless ``chrome`` is false, the ``sbkChrome`` property.

    The property lets an application write ``*[sbkChrome="true"]`` rules that reach the gallery's widgets but not the widgets of a
    story. It goes only on widgets that an application might style and that contain no story widget, so a widget that is an ancestor
    of the preview surface is marked with ``chrome=False`` and gets its name only. A widget that is already polished is polished
    again, because Qt matches style sheet selectors when a widget is polished.

    Args:
        widget: The widget to mark.
        name: The object name, in camel case with the ``sbk`` prefix. An internal child (a tab bar, a viewport, the input of an editor)
            has no name and is marked by the property alone.
        chrome: Whether the widget gets the ``sbkChrome`` property.
    """
    if name:
        widget.setObjectName(name)
    if chrome:
        widget.setProperty(CHROME_PROPERTY, True)  # noqa: FBT003 - a Qt property value, not a boolean parameter
    if widget.testAttribute(Qt.WidgetAttribute.WA_WState_Polished):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)


__all__ = ["CHROME_PROPERTY", "mark_chrome"]
