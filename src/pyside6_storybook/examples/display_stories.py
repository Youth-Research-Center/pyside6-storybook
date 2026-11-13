"""Display stories: label, progress bar, and the palette of the active theme."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from pyside6_storybook import BoolControl, ChoiceControl, IntControl, StoryContext, TextControl, story

_ALIGNMENTS = {"Left": Qt.AlignmentFlag.AlignLeft, "Center": Qt.AlignmentFlag.AlignHCenter, "Right": Qt.AlignmentFlag.AlignRight}
_ROLE = QPalette.ColorRole
_SWATCHES = (
    ("Window", _ROLE.Window, _ROLE.WindowText),
    ("Base", _ROLE.Base, _ROLE.Text),
    ("Alternate Base", _ROLE.AlternateBase, _ROLE.Text),
    ("Button", _ROLE.Button, _ROLE.ButtonText),
    ("Highlight", _ROLE.Highlight, _ROLE.HighlightedText),
    ("Tool Tip", _ROLE.ToolTipBase, _ROLE.ToolTipText),
)


@story(
    "Display/Label",
    controls=[
        TextControl("text", "A label wraps long text onto several lines when word wrap is on, instead of growing wider."),
        BoolControl("word_wrap", default=True),
        ChoiceControl("alignment", "Left", tuple(_ALIGNMENTS)),
    ],
)
def label(ctx: StoryContext) -> QWidget:
    """A ``QLabel``. Turn word wrap off to see the label grow to fit the text on one line."""
    widget = QLabel(ctx.args["text"])
    widget.setWordWrap(ctx.args["word_wrap"])
    widget.setAlignment(_ALIGNMENTS[ctx.args["alignment"]] | Qt.AlignmentFlag.AlignVCenter)
    return widget


@story(
    "Display/Progress Bar",
    controls=[IntControl("value", 40, 0, 100), BoolControl("text_visible", default=True), BoolControl("busy", default=False)],
)
def progress_bar(ctx: StoryContext) -> QWidget:
    """A ``QProgressBar``. ``busy`` gives it an empty range, which shows a busy indicator instead of a percentage."""
    bar = QProgressBar()
    if ctx.args["busy"]:
        bar.setRange(0, 0)
    else:
        bar.setRange(0, 100)
        bar.setValue(ctx.args["value"])
    bar.setTextVisible(ctx.args["text_visible"])
    return bar


@story("Display/Palette")
def palette(ctx: StoryContext) -> QWidget:
    """The colour roles of the active theme, each drawn in its own colours. It has no controls and reads ``ctx.theme``."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel(f"Theme: {ctx.theme}", widget))
    grid = QGridLayout()
    for index, (name, background, foreground) in enumerate(_SWATCHES):
        swatch = QLabel(name, widget)
        swatch.setFrameShape(QFrame.Shape.Box)
        swatch.setAutoFillBackground(True)
        swatch.setBackgroundRole(background)
        swatch.setForegroundRole(foreground)
        swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        swatch.setMargin(12)
        grid.addWidget(swatch, index // 3, index % 3)
    layout.addLayout(grid)
    return widget
