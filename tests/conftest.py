import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

import pyside6_storybook
from pyside6_storybook import BoolControl, IntControl, StoryContext, StoryRegistry, TextControl
from pyside6_storybook import registry as registry_module
from pyside6_storybook.themes import BuiltinThemes


@pytest.fixture
def restore_application_look(qapp: QApplication) -> Iterator[None]:
    """Put the application's style, palette, font and style sheet back after a test that changes them."""
    style_name = qapp.style().objectName()
    palette = QPalette(qapp.palette())
    font = QFont(qapp.font())
    style_sheet = qapp.styleSheet()
    try:
        yield
    finally:
        if qapp.style().objectName() != style_name:
            qapp.setStyle(style_name)
        qapp.setPalette(palette)
        if qapp.font() != font:
            qapp.setFont(font)
        qapp.setStyleSheet(style_sheet)


@pytest.fixture
def themes(qapp: QApplication, restore_application_look: None) -> Iterator[BuiltinThemes]:
    """Active built-in themes, deactivated after the test."""
    builtin_themes = BuiltinThemes()
    builtin_themes.activate(qapp)
    try:
        yield builtin_themes
    finally:
        builtin_themes.deactivate()


@pytest.fixture
def registry() -> StoryRegistry:
    """A registry of three stories built from stock Qt widgets; the last one has no controls."""
    stories = StoryRegistry()

    @stories.story("Inputs/Button", controls=[TextControl("text", "Click me"), BoolControl("enabled", default=True)])
    def button(ctx: StoryContext) -> QWidget:
        widget = QPushButton(str(ctx.args["text"]))
        widget.setEnabled(bool(ctx.args["enabled"]))
        return widget

    @stories.story("Display/Label", controls=[IntControl("size", 10, 1, 50)])
    def label(ctx: StoryContext) -> QWidget:
        return QLabel(f"{ctx.theme} {ctx.args['size']}")

    @stories.story("Display/Plain")
    def plain(ctx: StoryContext) -> QWidget:
        return QLabel("plain")

    return stories


@pytest.fixture
def stories(monkeypatch: pytest.MonkeyPatch) -> Iterator[StoryRegistry]:
    """A fresh default registry for tests that load story modules, with ``sys.path`` and ``sys.modules`` restored afterwards.

    Both bindings of the default registry are replaced: ``pyside6_storybook.registry.default_registry``, which ``@story`` reads, and
    ``pyside6_storybook.default_registry``, which a project's modules import. A reload replaces modules that were already imported,
    so the modules present before the test are put back too.
    """
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)
    monkeypatch.setattr(pyside6_storybook, "default_registry", isolated)
    monkeypatch.setattr(sys, "path", list(sys.path))
    modules_before = dict(sys.modules)
    try:
        yield isolated
    finally:
        for name in set(sys.modules) - set(modules_before):
            del sys.modules[name]
        sys.modules.update(modules_before)


@pytest.fixture(scope="module")
def restore_window_activation(qapp: QApplication) -> None:
    """Let the platform activate windows again after an earlier test ended the event loop (``run()`` does, in ``test_app.py``).

    The offscreen platform ignores activation requests once an event loop has quit, until the next loop runs, and a window an earlier
    test closed keeps the platform's focus until it is deleted. Both are cleared by deleting what is pending and running a loop. A test
    module that drives shortcuts or asserts focus uses it, together with ``show_active``.
    """
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTimer.singleShot(0, qapp.quit)
    qapp.exec()


def show_active(qtbot, window: QWidget) -> None:
    """Show a window and wait until the platform made it the active one, so shortcuts and focus behave as for a user."""
    window.show()
    window.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is window, timeout=5000)
