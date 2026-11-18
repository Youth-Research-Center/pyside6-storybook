"""``ExceptionCapture``: collects what reaches ``sys.excepthook`` and restores the hook."""

import sys

import pytest
from PySide6.QtCore import QObject, Signal

from pyside6_storybook.testing.exception_capture import ExceptionCapture


class _Emitter(QObject):
    fired = Signal()


def _raise() -> None:
    raise RuntimeError("slot boom")


def test_an_exception_in_a_slot_is_collected_with_its_traceback() -> None:
    emitter = _Emitter()
    emitter.fired.connect(_raise)

    with ExceptionCapture() as capture:
        emitter.fired.emit()

    assert len(capture.errors) == 1
    assert "RuntimeError: slot boom" in capture.errors[0]
    assert "in _raise" in capture.errors[0]


def test_the_previous_hook_is_restored_on_exit_and_when_the_block_raises() -> None:
    hook = sys.excepthook

    with ExceptionCapture():
        assert sys.excepthook is not hook
    assert sys.excepthook is hook

    with pytest.raises(ValueError, match="block"), ExceptionCapture():
        raise ValueError("block")
    assert sys.excepthook is hook
