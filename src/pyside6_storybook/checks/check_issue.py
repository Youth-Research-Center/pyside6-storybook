"""``CheckIssue``: one problem that a check found in a widget."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckIssue:
    """One problem found in one widget.

    Attributes:
        rule: The rule that failed, such as ``"name"`` or ``"focus"``; the same names ``checks_ignore`` takes.
        widget_class: The class name of the widget.
        object_name: The widget's ``objectName()``, or an empty string.
        path: The class names from the checked widget down to this one, each below the root with its index among the siblings of the
            same class, for example ``QWidget/QGroupBox[0]/QToolButton[1]``.
        message: What is wrong and how to fix it.
    """

    rule: str
    widget_class: str
    object_name: str
    path: str
    message: str

    def __str__(self) -> str:
        name = f" {self.object_name!r}" if self.object_name else ""
        return f"{self.rule}: {self.widget_class}{name} at {self.path}: {self.message}"


__all__ = ["CheckIssue"]
