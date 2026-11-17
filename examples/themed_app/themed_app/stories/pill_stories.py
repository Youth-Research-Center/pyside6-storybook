"""Stories for the pill button."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyside6_storybook import BoolControl, StoryContext, TextControl, story
from themed_app.widgets import PillButton


@story("Buttons/Pill", controls=[TextControl("text", "Save"), BoolControl("enabled", default=True)])
def pill(ctx: StoryContext) -> QWidget:
    """A pill button. The application style sheet gives it its colours, so it changes with the theme."""
    button = PillButton(ctx.args["text"])
    button.setEnabled(bool(ctx.args["enabled"]))
    return button


pill.variant("Disabled", args={"enabled": False})


@story("Buttons/Pill Row", controls=[TextControl("first", "Cancel"), TextControl("second", "Apply")])
def pill_row(ctx: StoryContext) -> QWidget:
    """Two pill buttons side by side."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.addWidget(PillButton(ctx.args["first"], row))
    layout.addWidget(PillButton(ctx.args["second"], row))
    return row
