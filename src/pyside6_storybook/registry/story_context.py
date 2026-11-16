"""``StoryContext``, what a story function receives, and the ``StoryFunction`` and ``Decorator`` types."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True, kw_only=True)
class StoryContext:
    """Everything a story function receives.

    Attributes:
        args: The current control values by control name. Stored as a read-only copy. Typed ``Any`` so a story can pass a value
            straight to Qt (``QSpinBox.setValue(ctx.args["count"])``); each value has the type of its control's default.
        theme: Name of the active theme.
    """

    args: Mapping[str, Any]
    theme: str = "Light"

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", MappingProxyType(dict(self.args)))


StoryFunction = Callable[[StoryContext], QWidget]
"""A story function: builds one widget in one state from a ``StoryContext``."""

Decorator = Callable[[QWidget, StoryContext], QWidget]
"""A decorator: receives the widget built so far and the story's context, and returns the widget to show instead. It returns the same
widget after configuring it, or a new wrapper that contains the received widget as a descendant."""


__all__ = ["Decorator", "StoryContext", "StoryFunction"]
