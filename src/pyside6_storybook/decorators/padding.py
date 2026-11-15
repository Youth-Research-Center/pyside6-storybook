"""``padding``: surround the story's widget with empty space."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from pyside6_storybook.decorators._checks import check_int
from pyside6_storybook.registry.story_context import StoryContext


class _Padding:
    def __init__(self, horizontal: int, vertical: int | None) -> None:
        self._horizontal = check_int("horizontal", horizontal)
        self._vertical = None if vertical is None else check_int("vertical", vertical)
        for name, value in (("horizontal", self._horizontal), ("vertical", self._vertical)):
            if value is not None and value < 0:
                raise ValueError(f"padding: {name} must not be negative, got {value}")

    def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
        vertical = self._horizontal if self._vertical is None else self._vertical
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(self._horizontal, vertical, self._horizontal, vertical)
        layout.addWidget(widget)
        return wrapper

    def __repr__(self) -> str:
        if self._vertical is None:
            return f"padding({self._horizontal})"
        return f"padding({self._horizontal}, {self._vertical})"


def padding(horizontal: int, vertical: int | None = None) -> _Padding:
    """Return a decorator that surrounds the widget with transparent space.

    Args:
        horizontal: The space in pixels to the left and to the right of the widget.
        vertical: The space in pixels above and below the widget; defaults to ``horizontal``.

    Returns:
        A decorator that puts the widget in a transparent wrapper with those margins.

    Raises:
        TypeError: If an argument is not an ``int``.
        ValueError: If an argument is negative.
    """
    return _Padding(horizontal, vertical)


__all__ = ["padding"]
