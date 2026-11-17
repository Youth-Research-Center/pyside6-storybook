"""Display stories: label, progress bar, and the palette of the active theme."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QLabel, QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from pyside6_storybook import BoolControl, ChoiceControl, ColorControl, EnumControl, IntControl, Layout, StoryContext, TextControl, story

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


_TOKEN_FALLBACKS = {
    "accent": QPalette.ColorRole.Accent,
    "highlighted_text": QPalette.ColorRole.HighlightedText,
    "border": QPalette.ColorRole.Mid,
}
"""The palette role a ``TokenBadge`` uses for each token the story did not pass."""


class TokenBadge(QWidget):
    """A rounded badge painted from design tokens: ``accent`` fill, ``highlighted_text`` text and a ``border`` outline.

    A token that is missing falls back to the matching palette role, so the badge also works with a plain ``StoryContext``.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._tokens: dict[str, object] = {}
        self.setAccessibleName("Token badge")
        self.setAccessibleDescription("A badge painted in the accent colour of the active theme.")

    def set_tokens(self, tokens: dict[str, object]) -> None:
        """Use these design tokens, such as ``dict(ctx.tokens)``, and repaint."""
        self._tokens = dict(tokens)
        self.update()

    def sizeHint(self) -> QSize:
        """Return a size derived from the font, so the badge follows the application font."""
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self._text) + 3 * metrics.height(), 2 * metrics.height())

    def _color(self, name: str) -> QColor:
        token = self._tokens.get(name)
        if isinstance(token, str) and QColor.isValidColorName(token):
            return QColor(token)
        return self.palette().color(QPalette.ColorGroup.Active, _TOKEN_FALLBACKS[name])

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the badge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QPen(self._color("border"))
        outline.setWidth(2)
        painter.setPen(outline)
        painter.setBrush(self._color("accent"))
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(self._color("highlighted_text"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


@story(
    "Display/Label",
    controls=[
        TextControl(
            "text",
            "A label wraps long text onto several lines when word wrap is on, instead of growing wider.",
            multiline=True,
            description="The label's text. Press Enter for a line break.",
        ),
        BoolControl("word_wrap", default=True, label="Word wrap"),
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
    controls=[
        IntControl("value", 40, 0, 100, slider=True, description="Ignored while the bar is busy."),
        BoolControl("text_visible", default=True),
        BoolControl("busy", default=False),
    ],
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


@story(
    "Display/Color Swatch",
    controls=[
        ColorControl("color", "#3a7bd5cc", alpha=True, description="Any colour; the last two digits are the opacity."),
        TextControl("text", "Sample"),
    ],
)
def color_swatch(ctx: StoryContext) -> QWidget:
    """A ``QLabel`` filled with a colour, in black or white text, whichever is easier to read on it.

    The control gives the story a ``QColor``, which a translucent colour keeps its opacity in; the text colour is chosen against the
    colour blended over the window colour, which is what is seen behind the text.
    """
    color: QColor = ctx.args["color"]
    widget = QLabel(ctx.args["text"])
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMargin(24)
    text = _readable_text_color(_blend_over(color, QApplication.palette().color(QPalette.ColorRole.Window)))
    widget.setStyleSheet(
        f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()}); color: {text.name()};"
    )
    return widget


def _blend_over(color: QColor, backdrop: QColor) -> QColor:
    """Return ``color`` laid over the opaque ``backdrop``, as it looks on the screen."""
    opacity = color.alphaF()
    return QColor(
        round(color.red() * opacity + backdrop.red() * (1 - opacity)),
        round(color.green() * opacity + backdrop.green() * (1 - opacity)),
        round(color.blue() * opacity + backdrop.blue() * (1 - opacity)),
    )


def _luminance(color: QColor) -> float:
    """Return the WCAG relative luminance of an opaque colour."""

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(color.red()) + 0.7152 * linear(color.green()) + 0.0722 * linear(color.blue())


def _readable_text_color(background: QColor) -> QColor:
    """Return black or white, whichever has the higher WCAG contrast ratio against the opaque ``background``."""
    luminance = _luminance(background)
    black_ratio = (luminance + 0.05) / 0.05
    white_ratio = 1.05 / (luminance + 0.05)
    return QColor(0, 0, 0) if black_ratio >= white_ratio else QColor(255, 255, 255)


@story(
    "Display/Alignment",
    controls=[
        EnumControl("alignment", Qt.AlignmentFlag.AlignCenter, description="A named Qt.AlignmentFlag, including combinations such as AlignCenter."),
        TextControl("text", "Aligned text"),
    ],
)
def alignment(ctx: StoryContext) -> QWidget:
    """A ``QLabel`` with an alignment chosen from ``Qt.AlignmentFlag``. The story receives the enum member itself."""
    widget = QLabel(ctx.args["text"])
    widget.setFrameShape(QFrame.Shape.Box)
    widget.setMinimumHeight(120)
    widget.setAlignment(ctx.args["alignment"])
    return widget


@story(
    "Display/Table",
    controls=[
        IntControl("rows", 8, 1, 50, slider=True),
        IntControl("columns", 4, 1, 12),
        BoolControl("alternating_rows", default=True, label="Alternating row colours"),
    ],
    layout=Layout.FILL,
)
def table(ctx: StoryContext) -> QWidget:
    """A ``QTableWidget`` that fills the preview. It grows and shrinks with the window, and scrolls inside itself."""
    widget = QTableWidget(ctx.args["rows"], ctx.args["columns"])
    widget.setAccessibleName("Example table")
    widget.setAlternatingRowColors(ctx.args["alternating_rows"])
    for row in range(ctx.args["rows"]):
        for column in range(ctx.args["columns"]):
            widget.setItem(row, column, QTableWidgetItem(f"R{row + 1}C{column + 1}"))
    return widget


@story("Display/Token Badge", controls=[TextControl("text", "Badge", description="The badge's text.")])
def token_badge(ctx: StoryContext) -> QWidget:
    """A custom widget painted from the active theme's design tokens. The story hands a copy of ``ctx.tokens`` to it with ``set_tokens``."""
    widget = TokenBadge(ctx.args["text"])
    widget.set_tokens(dict(ctx.tokens))
    return widget
