"""Input stories: line edit, spin boxes, combo box and slider."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit, QSlider, QSpinBox, QWidget

from pyside6_storybook import BoolControl, ChoiceControl, FloatControl, IntControl, StoryContext, TextControl, story

_ECHO_MODES = {"Normal": QLineEdit.EchoMode.Normal, "Password": QLineEdit.EchoMode.Password}
_FRUITS = ("Apple", "Banana", "Cherry")
_ORIENTATIONS = {"Horizontal": Qt.Orientation.Horizontal, "Vertical": Qt.Orientation.Vertical}


@story(
    "Inputs/Line Edit",
    controls=[
        TextControl("text", ""),
        TextControl("placeholder", "Type here…"),
        BoolControl("read_only", default=False),
        ChoiceControl("echo_mode", "Normal", tuple(_ECHO_MODES)),
    ],
)
def line_edit(ctx: StoryContext) -> QWidget:
    """A ``QLineEdit``. The placeholder shows only while the text is empty; ``Password`` echo mode hides what is typed."""
    edit = QLineEdit(ctx.args["text"])
    edit.setPlaceholderText(ctx.args["placeholder"])
    edit.setReadOnly(ctx.args["read_only"])
    edit.setEchoMode(_ECHO_MODES[ctx.args["echo_mode"]])
    return edit


@story("Inputs/Spin Box", controls=[IntControl("value", 5, -100, 100), IntControl("maximum", 10, 1, 100), TextControl("suffix", " items")])
def spin_box(ctx: StoryContext) -> QWidget:
    """A ``QSpinBox`` from 0 to ``maximum``. A ``value`` outside that range is clamped, which is how the widget behaves."""
    box = QSpinBox()
    box.setRange(0, ctx.args["maximum"])
    box.setSuffix(ctx.args["suffix"])
    box.setValue(ctx.args["value"])
    return box


@story("Inputs/Double Spin Box", controls=[FloatControl("value", 2.5, 0.0, 10.0), IntControl("decimals", 2, 0, 6)])
def double_spin_box(ctx: StoryContext) -> QWidget:
    """A ``QDoubleSpinBox`` from 0 to 10. Fewer ``decimals`` round the shown value."""
    box = QDoubleSpinBox()
    box.setRange(0.0, 10.0)
    box.setDecimals(ctx.args["decimals"])
    box.setValue(ctx.args["value"])
    return box


@story("Inputs/Combo Box", controls=[ChoiceControl("selected", "Banana", _FRUITS), BoolControl("editable", default=False)])
def combo_box(ctx: StoryContext) -> QWidget:
    """A ``QComboBox``. An editable combo box also accepts typed text that is not in the list."""
    box = QComboBox()
    box.addItems(_FRUITS)
    box.setCurrentText(ctx.args["selected"])
    box.setEditable(ctx.args["editable"])
    return box


@story("Inputs/Slider", controls=[IntControl("value", 50, 0, 100), ChoiceControl("orientation", "Horizontal", tuple(_ORIENTATIONS))])
def slider(ctx: StoryContext) -> QWidget:
    """A ``QSlider`` from 0 to 100, lying down or standing up."""
    widget = QSlider(_ORIENTATIONS[ctx.args["orientation"]])
    widget.setRange(0, 100)
    widget.setValue(ctx.args["value"])
    return widget
