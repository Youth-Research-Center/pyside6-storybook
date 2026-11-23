"""``StoryContext``, what a story function receives, and the ``StoryFunction`` and ``Decorator`` types."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType, ModuleType
from typing import Any, Protocol

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QMetaMethod, QObject, Qt, SignalInstance
from PySide6.QtWidgets import QWidget

_logger = logging.getLogger(__name__)

_NOISY_SIGNALS = frozenset({"updateRequest"})
"""Signals that ``log_signals`` leaves out because they fire on every repaint."""

_ENUM_OWNER_MODULES = (QtCore, QtGui, QtWidgets)
"""Where the owner of an enum type named in a signal's signature is looked up first."""


class ActionSink(Protocol):
    """Receives the actions a story logs with ``StoryContext.log``, ``log_signal`` and ``log_signals``.

    The gallery's Actions panel is one.
    """

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


def _signal_methods(obj: QObject) -> dict[str, list[QMetaMethod]]:
    """Return the signal entries of ``obj`` by name, in declaration order, from the classes below ``QWidget`` (``QObject`` for a non-widget).

    A name that has default arguments has several entries (``clicked(bool)`` and ``clicked()``). ``_NOISY_SIGNALS`` are left out.
    """
    meta = obj.metaObject()
    stop = "QWidget" if isinstance(obj, QWidget) else "QObject"
    ancestor = meta
    while ancestor is not None and ancestor.className() != stop:
        ancestor = ancestor.superClass()
    base = ancestor.methodCount() if ancestor is not None else 0
    methods: dict[str, list[QMetaMethod]] = {}
    for index in range(base, meta.methodCount()):
        method = meta.method(index)
        if method.methodType() != QMetaMethod.MethodType.Signal:
            continue
        name = bytes(method.name().data()).decode()
        if name not in _NOISY_SIGNALS:
            methods.setdefault(name, []).append(method)
    return methods


def _resolve_parameter_types(method: QMetaMethod, modules: Iterable[ModuleType]) -> bool:
    """Make Python create the enum types in the signature of ``method``, and return whether every parameter type can be converted.

    PySide6 creates the Python type of an enum when its owner is first used from Python, and until then cannot convert a signal's argument
    of that type. A type name without ``::`` needs nothing. A name with ``::`` and ``<`` (``std::chrono::...``) cannot be resolved. Any
    other name is ``Owner::Enum``, which is looked up as an attribute of ``Owner`` in ``modules``.

    Args:
        method: A signal entry.
        modules: The modules that may hold the owner classes, searched in order.

    Returns:
        ``False`` when a type could not be resolved.
    """
    for raw in method.parameterTypes():
        name = bytes(raw.data()).decode().removeprefix("const ").rstrip("*& ").strip()
        if "::" not in name:
            continue
        if "<" in name:
            return False
        owner_name, *rest = name.split("::")
        target = next((getattr(module, owner_name) for module in modules if hasattr(module, owner_name)), None)
        if target is None:
            return False
        for part in rest:
            target = getattr(target, part, None)
            if target is None:
                return False
    return True


@dataclass(frozen=True, kw_only=True)
class StoryContext:
    """Everything a story function receives.

    Attributes:
        args: The current control values by control name. Stored as a read-only copy. Typed ``Any`` so a story can pass a value
            straight to Qt (``QSpinBox.setValue(ctx.args["count"])``); each value has the type of its control's default.
        theme: Name of the active theme.
        actions: Where ``log``, ``log_signal`` and ``log_signals`` send actions. The gallery passes its Actions panel; it is ``None``
            otherwise, and then all three methods do nothing. It does not take part in equality or ``repr``.
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

        ``log_signals`` does this for every signal of an object. The row shows the arguments the signal delivers to a slot:
        ``QPushButton.clicked`` delivers none, ``valueChanged`` delivers the new value. The connection ends when the signal's
        widget is deleted, and the slot holds no reference to the widget.

        Args:
            signal: A bound signal, such as ``button.clicked``.
            name: The name to show; the signal's own name when omitted.

        Raises:
            TypeError: If there is a sink and ``name`` is omitted and the signal's name cannot be found.
        """
        if self.actions is None:
            return
        signal.connect(_forward(self.actions, name or _signal_name(signal)))

    def log_signals(self, obj: QObject, *, exclude: Iterable[str] = ()) -> None:
        """Show every emission of every signal of ``obj`` in the gallery's Actions panel. Without a sink this does nothing.

        It logs the signals that the classes of ``obj`` declare, below ``QWidget`` for a widget (``clicked``, ``toggled``, ``valueChanged``)
        and below ``QObject`` for any other object (the ``selectionChanged`` of an item view's ``selectionModel()``), and leaves out the
        ones every widget has (``objectNameChanged``, ``windowTitleChanged``, ``customContextMenuRequested``) and ``updateRequest``, which
        fires on every repaint. Use ``log_signal`` for one of those. Each signal is logged as ``log_signal`` logs it, with the arguments
        of its default overload.

        Call it after configuring the object, or the emissions of the setup (``addItems`` emits ``currentIndexChanged``) are logged on
        every render. The connections end when ``obj`` is deleted, so an object that outlives the story's widget gets one more connection
        per render. Calling it twice connects twice. A signal whose argument type PySide6 cannot convert is not connected, and one
        warning names it.

        Args:
            obj: The object whose signals to log, such as the widget the story returns, or a child of it.
            exclude: Names of signals to leave out, such as ``("highlighted",)``. A name that ``obj`` has no signal of is logged as a
                warning that lists its signals, and does not raise, because the signals differ between Qt versions.

        Raises:
            TypeError: If there is a sink and ``exclude`` is a string, or ``obj`` is not a ``QObject``. A bound signal gets a message
                that points to ``log_signal``.
        """
        if self.actions is None:
            return
        if isinstance(exclude, str):
            raise TypeError("pass a tuple of names as exclude, not a string")
        if isinstance(obj, SignalInstance):
            raise TypeError("log_signals takes a QObject; use log_signal for one signal")
        if not isinstance(obj, QObject):
            raise TypeError(f"log_signals takes a QObject, not {type(obj).__name__}")
        excluded = set(exclude)
        methods = _signal_methods(obj)
        class_name = type(obj).__name__
        unknown = sorted(excluded - methods.keys() - _NOISY_SIGNALS)
        if unknown:
            _logger.warning("log_signals: %s has no signal named %s; its signals are %s", class_name, ", ".join(unknown), ", ".join(methods))
        modules = [*_ENUM_OWNER_MODULES, *(sys.modules[cls.__module__] for cls in type(obj).__mro__ if cls.__module__ in sys.modules)]
        wanted = {name: entries for name, entries in methods.items() if name not in excluded}
        resolved = {name: all(_resolve_parameter_types(entry, modules) for entry in entries) for name, entries in wanted.items()}
        skipped = [name for name, ok in resolved.items() if not ok]
        if skipped:
            _logger.warning("log_signals: %s of %s not connected, an argument type cannot be converted", ", ".join(skipped), class_name)
        for name, ok in resolved.items():
            if ok:
                getattr(obj, name).connect(_forward(self.actions, name))

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
