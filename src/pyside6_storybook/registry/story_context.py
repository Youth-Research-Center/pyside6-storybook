"""``StoryContext``, what a story function receives, and the ``StoryFunction`` type."""

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


__all__ = ["StoryContext", "StoryFunction"]
