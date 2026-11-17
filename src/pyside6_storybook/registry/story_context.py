"""``StoryContext``, what a story function receives, and the ``StoryFunction`` and ``Decorator`` types."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtWidgets import QWidget


class ActionSink(Protocol):
    """Receives the actions a story logs with ``StoryContext.log`` and ``StoryContext.log_signal``; the gallery's Actions panel is one."""

    def record(self, name: str, args: tuple[object, ...]) -> None:
        """Record one action.

        Args:
            name: The action's name, such as ``"clicked"``.
            args: The arguments the action carried.
        """
        ...


def _signal_name(signal: SignalInstance) -> str:
    """Return the name of a signal from its repr, ``<PySide6.QtCore.SignalInstance clicked() at 0x...>``, or raise ``TypeError``."""
    text = repr(signal)
    marker = "SignalInstance "
    start = text.find(marker)
    end = text.find("(", start + len(marker)) if start >= 0 else -1
    name = text[start + len(marker) : end].strip() if end >= 0 else ""
    if not name or " " in name:
        raise TypeError(f"Cannot find the name of signal {text}; pass name= to log_signal")
    return name


def _forward(sink: ActionSink, name: str) -> Callable[..., None]:
    """Return a slot that records ``name`` with the signal's arguments; it holds the sink and the name, never a widget."""

    def record(*args: object) -> None:
        sink.record(name, args)

    return record


@dataclass(frozen=True, kw_only=True)
class StoryContext:
    """Everything a story function receives.

    Attributes:
        args: The current control values by control name. Stored as a read-only copy. Typed ``Any`` so a story can pass a value
            straight to Qt (``QSpinBox.setValue(ctx.args["count"])``); each value has the type of its control's default.
        theme: Name of the active theme.
        actions: Where ``log`` and ``log_signal`` send actions. The gallery passes its Actions panel; it is ``None`` otherwise, and
            then both methods do nothing. It does not take part in equality or ``repr``.
        tokens: The design tokens of the active theme, by name, as the theme provider returns them from its optional ``tokens()``
            method (the built-in themes give colours such as ``"accent"`` as ``#rrggbb`` strings). Stored as a read-only copy and
            empty by default, so a story reads ``ctx.tokens.get("accent")`` and handles a missing token. It does not appear in ``repr``.
        color_scheme: Whether the active theme is light or dark, as a ``Qt.ColorScheme``. The theme provider gives it through its
            optional ``color_scheme()`` method; without one the gallery guesses from the application palette's ``Window`` colour.
            ``Qt.ColorScheme.Unknown`` by default.
    """

    args: Mapping[str, Any]
    theme: str = "Light"
    actions: ActionSink | None = field(default=None, compare=False, repr=False, kw_only=True)
    tokens: Mapping[str, Any] = field(default_factory=dict, kw_only=True, repr=False)
    color_scheme: Qt.ColorScheme = field(default=Qt.ColorScheme.Unknown, kw_only=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", MappingProxyType(dict(self.args)))
        object.__setattr__(self, "tokens", MappingProxyType(dict(self.tokens)))

    def log_signal(self, signal: SignalInstance, name: str | None = None) -> None:
        """Show every emission of ``signal`` in the gallery's Actions panel. Without a sink this does nothing.

        The row shows the arguments the signal delivers to a slot: ``QPushButton.clicked`` delivers none, ``valueChanged`` delivers the
        new value. The connection ends when the signal's widget is deleted, and the slot holds no reference to the widget.

        Args:
            signal: A bound signal, such as ``button.clicked``.
            name: The name to show; the signal's own name when omitted.

        Raises:
            TypeError: If there is a sink and ``name`` is omitted and the signal's name cannot be found.
        """
        if self.actions is None:
            return
        signal.connect(_forward(self.actions, name or _signal_name(signal)))

    def log(self, name: str, *args: object) -> None:
        """Show an action in the gallery's Actions panel. Without a sink this does nothing.

        Args:
            name: The action's name.
            *args: The arguments to show.
        """
        if self.actions is not None:
            self.actions.record(name, args)


StoryFunction = Callable[[StoryContext], QWidget]
"""A story function: builds one widget in one state from a ``StoryContext``."""

Decorator = Callable[[QWidget, StoryContext], QWidget]
"""A decorator: receives the widget built so far and the story's context, and returns the widget to show instead. It returns the same
widget after configuring it, or a new wrapper that contains the received widget as a descendant."""


__all__ = ["ActionSink", "Decorator", "StoryContext", "StoryFunction"]
