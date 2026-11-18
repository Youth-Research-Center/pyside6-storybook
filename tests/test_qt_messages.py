import re
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QMessageLogContext, QtMsgType, qDebug, qInstallMessageHandler, qWarning

from pyside6_storybook.testing.qt_messages import QtMessage, QtMessageCollector


@pytest.fixture(autouse=True)
def restore_handler() -> Iterator[None]:
    """Put back the Qt message handler (pytest-qt's capture) that was installed before the test."""
    original = qInstallMessageHandler(None)
    qInstallMessageHandler(original)
    try:
        yield
    finally:
        qInstallMessageHandler(original)


def _current_handler() -> object:
    current = qInstallMessageHandler(None)
    qInstallMessageHandler(current)
    return current


def test_warnings_are_collected_and_debug_messages_are_not() -> None:
    with QtMessageCollector() as collector:
        qDebug("just a note")
        qWarning("careful")

    assert collector.messages == [QtMessage("warning", "careful")]
    assert str(collector.messages[0]) == "warning: careful"


def test_the_previous_handler_still_receives_every_message_and_is_reinstalled() -> None:
    received: list[tuple[QtMsgType, str]] = []

    def previous(kind: QtMsgType, context: QMessageLogContext, message: str) -> None:
        received.append((kind, message))

    qInstallMessageHandler(previous)
    try:
        with QtMessageCollector():
            qDebug("note")
            qWarning("careful")
        assert _current_handler() is previous
    finally:
        qInstallMessageHandler(None)

    assert received == [(QtMsgType.QtDebugMsg, "note"), (QtMsgType.QtWarningMsg, "careful")]


def test_without_a_previous_handler_a_message_goes_to_standard_error(capfd: pytest.CaptureFixture[str]) -> None:
    qInstallMessageHandler(None)

    with QtMessageCollector():
        qWarning("to stderr")

    assert "to stderr" in capfd.readouterr().err


def test_unexcused_drops_the_messages_a_pattern_matches() -> None:
    with QtMessageCollector() as collector:
        qWarning("This plugin does not support propagateSizeHints()")
        qWarning("something else")

    patterns = (re.compile("propagateSizeHints"),)

    assert [message.text for message in collector.unexcused(patterns)] == ["something else"]
    assert len(collector.unexcused(())) == 2


def test_a_pattern_is_searched_in_the_text_without_the_kind() -> None:
    with QtMessageCollector() as collector:
        qWarning("exact")

    assert collector.unexcused((re.compile("^exact$"),)) == []


def test_install_and_uninstall_are_idempotent() -> None:
    before = _current_handler()
    collector = QtMessageCollector()
    collector.install()
    collector.install()
    collector.uninstall()
    collector.uninstall()

    assert _current_handler() is before
