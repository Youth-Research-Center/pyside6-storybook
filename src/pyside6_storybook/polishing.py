"""Work around a Qt crash around application style sheets: polish every widget before the style sheet changes.

Qt crashes in ``QApplication.setStyleSheet`` (in ``QWidget::style()``) when a widget that was never polished existed while the
application style sheet was cleared, and that widget was deleted after a style sheet was set again. It happens with PySide6 6.8 to
6.12 on every platform. A widget is polished when it is first shown or by ``ensurePolished()``; a hidden widget that was never shown
(another tab's page, a hidden label, a preview that was replaced) stays unpolished. A polished widget is safe, so the gallery polishes
its widgets after building them and the library polishes every widget before it changes the style sheet itself.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


def polish_all_widgets() -> None:
    """Polish every widget of the application that has not been polished yet; a no-op for those that have."""
    for widget in QApplication.allWidgets():
        widget.ensurePolished()


__all__ = ["polish_all_widgets"]
