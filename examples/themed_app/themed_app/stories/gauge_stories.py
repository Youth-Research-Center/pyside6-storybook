"""Stories for the gauge, which is painted from the active theme's design tokens."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pyside6_storybook import IntControl, StoryContext, story
from themed_app.widgets import Gauge


@story("Meters/Gauge", controls=[IntControl("value", 65, 0, 100, description="The percentage the gauge shows.")])
def gauge(ctx: StoryContext) -> QWidget:
    """A gauge painted from the design tokens. The story hands ``ctx.tokens`` to the widget with ``set_tokens``."""
    widget = Gauge()
    widget.set_tokens(ctx.tokens)
    widget.value = ctx.args["value"]
    return widget


gauge.variant("Empty", args={"value": 0})
gauge.variant("Full", args={"value": 100})
