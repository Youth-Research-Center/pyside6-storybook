"""``QtMessageCollector``: collect the Qt warnings logged while a story renders, and the patterns that excuse some of them (internal)."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from types import TracebackType
from typing import NamedTuple, Self

from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

_COLLECTED = {QtMsgType.QtWarningMsg: "warning", QtMsgType.QtCriticalMsg: "critical", QtMsgType.QtFatalMsg: "fatal"}


class QtMessage(NamedTuple):
    """A collected Qt message: ``kind`` is ``"warning"``, ``"critical"`` or ``"fatal"``."""

    kind: str
    text: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.text}"


class QtMessageCollector:
    """A context manager that installs a Qt message handler, collects warnings, critical and fatal messages, and chains to the old one.

    The handler that was installed before (pytest-qt's capture, for one) still receives every message. Without one, a message is
    written to standard error, as Qt's default handler does.

    Attributes:
        messages: The collected messages, in order.
    """

    def __init__(self) -> None:
        self.messages: list[QtMessage] = []
        self._previous: object = None
        self._installed = False

    def __enter__(self) -> Self:
        self.install()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None:
        self.uninstall()

    def install(self) -> None:
        """Install the handler; does nothing when it is installed."""
        if self._installed:
            return
        self._previous = qInstallMessageHandler(self._handle)
        self._installed = True

    def uninstall(self) -> None:
        """Reinstall the handler that was there before; does nothing when this one is not installed."""
        if not self._installed:
            return
        self._installed = False
        qInstallMessageHandler(self._previous)  # ty: ignore[invalid-argument-type]

    def unexcused(self, patterns: Sequence[re.Pattern[str]]) -> list[QtMessage]:
        """Return the collected messages that no pattern matches (``re.search`` on the message text)."""
        return [message for message in self.messages if not any(pattern.search(message.text) for pattern in patterns)]

    def _handle(self, kind: QtMsgType, context: QMessageLogContext, message: str) -> None:
        label = _COLLECTED.get(kind)
        if label is not None:
            self.messages.append(QtMessage(label, message))
        if callable(self._previous):
            self._previous(kind, context, message)
        else:
            sys.stderr.write(f"{message}\n")


__all__ = ["QtMessage", "QtMessageCollector"]
