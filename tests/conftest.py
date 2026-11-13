import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from collections.abc import Iterator

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from pyside6_storybook import BoolControl, IntControl, StoryContext, StoryRegistry, TextControl
from pyside6_storybook import registry as registry_module
from pyside6_storybook.themes import BuiltinThemes


@pytest.fixture
def restore_application_look(qapp: QApplication) -> Iterator[None]:
    """Put the application's style, palette and style sheet back after a test that changes them."""
    style_name = qapp.style().objectName()
    palette = QPalette(qapp.palette())
    style_sheet = qapp.styleSheet()
    try:
        yield
    finally:
        if qapp.style().objectName() != style_name:
            qapp.setStyle(style_name)
        qapp.setPalette(palette)
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
    """A fresh default registry for tests that load story modules, with ``sys.path`` and ``sys.modules`` restored afterwards."""
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)
    monkeypatch.setattr(sys, "path", list(sys.path))
    modules_before = set(sys.modules)
    try:
        yield isolated
    finally:
        for name in set(sys.modules) - modules_before:
            del sys.modules[name]
