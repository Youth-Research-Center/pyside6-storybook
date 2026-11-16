"""Button stories: a push button and a check box."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QPushButton, QWidget

from pyside6_storybook import BoolControl, Layout, StoryContext, TextControl, story


@story(
    "Buttons/Push Button/Default",
    controls=[TextControl("text", "Push me"), BoolControl("enabled", default=True), BoolControl("checkable", default=False)],
    layout=Layout.CENTERED,
)
def push_button(ctx: StoryContext) -> QWidget:
    """A ``QPushButton`` at its natural size, centred in the preview. Edit its text, disable it, or make it checkable.

    Clicking it logs ``clicked`` in the Actions tab.
    """
    button = QPushButton(ctx.args["text"])
    button.setEnabled(ctx.args["enabled"])
    button.setCheckable(ctx.args["checkable"])
    ctx.log_signal(button.clicked)
    return button


push_button.variant("Disabled", args={"enabled": False})
push_button.variant("Checkable", args={"checkable": True, "text": "Toggle me"})


@story(
    "Buttons/Check Box",
    controls=[TextControl("text", "Remember me"), BoolControl("checked", default=False), BoolControl("tristate", default=False)],
)
def check_box(ctx: StoryContext) -> QWidget:
    """A ``QCheckBox``. ``tristate`` adds a third, partially checked state that clicking cycles through."""
    box = QCheckBox(ctx.args["text"])
    box.setTristate(ctx.args["tristate"])
    box.setChecked(ctx.args["checked"])
    return box
