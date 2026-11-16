"""``fixed_size``: give the story's widget an exact size."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pyside6_storybook.decorators._checks import check_int
from pyside6_storybook.registry.story_context import StoryContext


class _FixedSize:
    def __init__(self, width: int, height: int) -> None:
        self._width = check_int("width", width)
        self._height = check_int("height", height)
        for name, value in (("width", self._width), ("height", self._height)):
            if value <= 0:
                raise ValueError(f"fixed_size: {name} must be positive, got {value}")

    def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
        widget.setFixedSize(self._width, self._height)
        return widget

    def __repr__(self) -> str:
        return f"fixed_size({self._width}, {self._height})"


def fixed_size(width: int, height: int) -> _FixedSize:
    """Return a decorator that gives the widget a fixed size.

    Args:
        width: The width in pixels.
        height: The height in pixels.

    Returns:
        A decorator that calls ``setFixedSize`` on the widget it receives and returns that widget, without a wrapper.

    Raises:
        TypeError: If an argument is not an ``int``.
        ValueError: If an argument is not positive.
    """
    return _FixedSize(width, height)


__all__ = ["fixed_size"]
