"""``ExceptionCapture``: collect the exceptions Qt reports through ``sys.excepthook`` while a story renders (internal)."""

from __future__ import annotations

import sys
import traceback
from types import TracebackType
from typing import Self


class ExceptionCapture:
    """A context manager that replaces ``sys.excepthook`` with one that collects the exceptions, and restores the old hook on exit.

    PySide6 hands an exception raised in a Python override of a Qt virtual method (a ``paintEvent``, for one) or in a slot to
    ``sys.excepthook`` instead of raising it to the caller, so without a capture such an exception is only printed.

    Attributes:
        errors: The formatted tracebacks of the collected exceptions, in order.
    """

    def __init__(self) -> None:
        self.errors: list[str] = []
        self._previous = sys.excepthook

    def __enter__(self) -> Self:
        self._previous = sys.excepthook
        sys.excepthook = self._hook
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        sys.excepthook = self._previous

    def _hook(self, exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        self.errors.append("".join(traceback.format_exception(exc_type, exc, tb)))


__all__ = ["ExceptionCapture"]
