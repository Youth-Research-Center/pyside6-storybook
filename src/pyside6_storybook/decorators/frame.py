"""``frame``: draw a border around the story's widget."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from pyside6_storybook.registry.story_context import StoryContext


class _Frame:
    def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
        wrapper = QFrame()
        wrapper.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return wrapper

    def __repr__(self) -> str:
        return "frame()"


def frame() -> _Frame:
    """Return a decorator that draws a panel border around the widget.

    Returns:
        A decorator that puts the widget in a ``QFrame`` with the ``StyledPanel`` shape and no margins inside the border. The border
        is drawn by the application's style from the palette, so it follows the theme.
    """
    return _Frame()


__all__ = ["frame"]
