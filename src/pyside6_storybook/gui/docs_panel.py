"""``DocsPanel``: the Docs tab, which describes the selected story: its docstrings, controls, sibling stories and source."""

from __future__ import annotations

import functools
import html
import inspect
import sys
from collections.abc import Mapping

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.controls import (
    BoolControl,
    ChoiceControl,
    ColorControl,
    Control,
    EnumControl,
    FileControl,
    FloatControl,
    IntControl,
    TextControl,
)
from pyside6_storybook.gui.icons import ActionIcons
from pyside6_storybook.registry import Story, StoryRegistry

NO_CONTROLS_MESSAGE = "No controls."
NO_SOURCE_MESSAGE = "Source not available for this story."
VARIANT_CAPTION = "Starting values of this variant."
CONTROLS_HEADERS = ("Name", "Type", "Default", "Range or options")
NO_FILE_TEXT = "(none)"

_MARGIN = 10
_SPACING = 8
_SECTION_SPACING = 6
_MAX_SOURCE_LINES = 30
_SELECTABLE_TEXT = Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
_LINK_TEXT = Qt.TextInteractionFlag.LinksAccessibleByKeyboard | Qt.TextInteractionFlag.LinksAccessibleByMouse


def controls_rows(controls: tuple[Control, ...], values: Mapping[str, object]) -> list[tuple[str, str, str, str]]:
    """Describe controls as table rows: name, type, default and range or options.

    Args:
        controls: The controls of a story, in order.
        values: The value each control starts with, by control name, as ``Story.default_args()`` returns them.

    Returns:
        One ``(name, type, default, range or options)`` tuple of text per control; the last column is empty when there is nothing to say.
    """
    return [_control_row(control, values.get(control.name, control.default)) for control in controls]


def _control_row(control: Control, value: object) -> tuple[str, str, str, str]:
    name = control.name
    if isinstance(control, TextControl):
        return (name, "multiline text" if control.multiline else "text", repr(value), "")
    if isinstance(control, BoolControl):
        return (name, "bool", str(value), "")
    if isinstance(control, ChoiceControl):
        return (name, "choice", str(value), ", ".join(control.options))
    if isinstance(control, IntControl):
        limits = f"{control.minimum}..{control.maximum}"
        return (name, "int", str(value), limits if control.step == 1 else f"{limits}, step {control.step}")
    if isinstance(control, FloatControl):
        limits = f"{control.minimum!r}..{control.maximum!r}, step {control.effective_step!r}, decimals {control.effective_decimals}"
        return (name, "float", repr(value), limits)
    if isinstance(control, ColorControl):
        color = control.coerce(value)
        digits = f"{color.red():02x}{color.green():02x}{color.blue():02x}"
        return (name, "colour", f"#{digits}{color.alpha():02x}" if control.alpha else f"#{digits}", "with alpha" if control.alpha else "")
    if isinstance(control, EnumControl):
        member = control.coerce(value)
        return (name, type(control.default).__qualname__, str(member.name), ", ".join(str(option.name) for option in control.options))
    if isinstance(control, FileControl):
        return (name, "file", str(value) if value else NO_FILE_TEXT, control.filter)
    raise TypeError(f"Unsupported control {control!r}")


class _SourceView(QPlainTextEdit):
    """A read-only view of source code that is as tall as its lines (at most ``_MAX_SOURCE_LINES``), whatever the font."""

    def __init__(self, source: str, parent: QWidget) -> None:
        super().__init__(source, parent)
        self._lines = min(max(source.count("\n") + 1, 1), _MAX_SOURCE_LINES)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        """Return a height for the lines, the frame, the document margins and the horizontal scroll bar."""
        hint = super().sizeHint()
        height = self.fontMetrics().lineSpacing() * self._lines + 2 * self.frameWidth() + 2 * _SPACING
        return QSize(hint.width(), height + self.horizontalScrollBar().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        """Return the same height as ``sizeHint`` and the usual minimum width."""
        return QSize(super().minimumSizeHint().width(), self.sizeHint().height())


class DocsPanel(QWidget):
    """What the gallery knows about a story, top to bottom: the module's and the story's docstrings, the controls, the sibling stories
    and the source code.

    The panel has no scroll bars of its own; the gallery window puts it in a ``QScrollArea``. Its content does not depend on control
    values, so the window shows a story once per selection.

    Signals:
        storyRequested(str): The id of a sibling story whose link was activated.
    """

    storyRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, icons: ActionIcons | None = None) -> None:
        """Create the panel, empty.

        Args:
            parent: The owning widget.
            icons: The registry that tints the Copy button's icon. ``None`` gives the panel its own, retinted when its palette changes;
                the gallery window passes its own, which it retints.
        """
        super().__init__(parent)
        self.setObjectName("docsPanel")
        self._own_icons = icons is None
        self._icons = icons if icons is not None else ActionIcons()
        self._source = ""
        self._content: QWidget | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._layout.setSpacing(0)

    def show_story(self, story: Story, registry: StoryRegistry) -> None:
        """Describe a story, replacing what the panel showed.

        Args:
            story: The story to describe.
            registry: The registry the story is in, which lists its sibling stories.
        """
        self.clear()
        content = QWidget(self)
        content.setObjectName("docsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SPACING)
        self._content = content
        self._layout.addWidget(content)

        module_doc = _module_doc(story)
        if module_doc:
            layout.addWidget(self._section("Component description", self._text(module_doc, "docsModuleDoc", content), content))
        if story.doc:
            layout.addWidget(self._section("Story description", self._text(story.doc, "docsStoryDoc", content), content))
        layout.addWidget(self._section("Controls", self._controls_body(story, content), content))
        siblings = _siblings(story, registry)
        if len(siblings) > 1 and story.component is not None:
            layout.addWidget(self._section(f"Stories of {story.component}", self._siblings_body(story, siblings, content), content))
        layout.addWidget(self._section("Source", self._source_body(story, content), content))
        layout.addStretch(1)

    def clear(self) -> None:
        """Remove what the panel shows."""
        content = self._content
        self._content = None
        self._source = ""
        if content is not None:
            self._layout.removeWidget(content)
            content.hide()
            content.deleteLater()

    def source_text(self) -> str:
        """Return the source code shown, or an empty string when none is."""
        return self._source

    def changeEvent(self, event: QEvent) -> None:
        """Render the Copy button's icon again when the palette changes, if the panel has its own icon registry."""
        super().changeEvent(event)
        if self._own_icons and event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self._icons.retint(self.palette())

    def _section(self, title: str, body: QWidget, parent: QWidget) -> QWidget:
        section = QWidget(parent)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SECTION_SPACING)
        heading = QLabel(title, section)
        heading.setObjectName("docsHeading")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        layout.addWidget(body)
        return section

    @staticmethod
    def _text(text: str, object_name: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName(object_name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(_SELECTABLE_TEXT)
        label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return label

    def _controls_body(self, story: Story, parent: QWidget) -> QWidget:
        if not story.controls:
            return self._text(NO_CONTROLS_MESSAGE, "docsNoControls", parent)
        body = QWidget(parent)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SECTION_SPACING)
        if story.variant_of is not None:
            layout.addWidget(self._text(VARIANT_CAPTION, "docsVariantCaption", body))
        layout.addWidget(self._controls_table(controls_rows(story.controls, story.default_args()), body))
        return body

    @staticmethod
    def _controls_table(rows: list[tuple[str, str, str, str]], parent: QWidget) -> QTableWidget:
        table = QTableWidget(len(rows), len(CONTROLS_HEADERS), parent)
        table.setObjectName("docsControlsTable")
        table.setAccessibleName("Controls")
        table.setHorizontalHeaderLabels(list(CONTROLS_HEADERS))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setWordWrap(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for row, cells in enumerate(rows):
            for column, text in enumerate(cells):
                table.setItem(row, column, QTableWidgetItem(text))
        table.resizeRowsToContents()
        # The table is as tall as its rows, whatever the font, without a pixel height of its own.
        table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        columns = sum(table.columnWidth(column) for column in range(len(CONTROLS_HEADERS)))
        table.setMinimumWidth(columns + table.verticalHeader().width() + 2 * table.frameWidth())
        return table

    def _siblings_body(self, story: Story, siblings: list[Story], parent: QWidget) -> QWidget:
        body = QWidget(parent)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for sibling in siblings:
            if sibling is story:
                label = self._text(f"{sibling.name} (this story)", "docsSiblingCurrent", body)
            else:
                label = QLabel(f'<a href="{html.escape(sibling.id)}">{html.escape(sibling.name)}</a>', body)
                label.setObjectName("docsSiblingLink")
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setTextInteractionFlags(_LINK_TEXT)
                label.setAccessibleName(f"Open {sibling.id}")
                label.linkActivated.connect(self.storyRequested)
            layout.addWidget(label)
        return body

    def _source_body(self, story: Story, parent: QWidget) -> QWidget:
        try:
            source = inspect.getsource(story.function)
        except (OSError, TypeError):
            self._source = ""
            return self._text(NO_SOURCE_MESSAGE, "docsNoSource", parent)
        self._source = source
        body = QWidget(parent)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SECTION_SPACING)

        copy_button = QPushButton("Copy", body)
        copy_button.setObjectName("docsCopyButton")
        copy_button.setAccessibleName("Copy source")
        copy_button.setAccessibleDescription("Copy the story's source code to the clipboard")
        copy_button.setAutoDefault(False)
        self._icons.bind(copy_button, "copy")
        copy_button.clicked.connect(self._copy_source)
        buttons = QHBoxLayout()
        buttons.addWidget(copy_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        view = _SourceView(source, body)
        view.setObjectName("docsSource")
        view.setAccessibleName("Source")
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        point_size = QApplication.font().pointSizeF()
        if point_size > 0:
            font.setPointSizeF(point_size)
        elif QApplication.font().pixelSize() > 0:
            font.setPixelSize(QApplication.font().pixelSize())
        view.setFont(font)
        view.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(view)
        return body

    def _copy_source(self) -> None:
        QApplication.clipboard().setText(self._source)


def _module_doc(story: Story) -> str:
    """Return the docstring of the module the story function was defined in, or an empty string when there is no such module.

    For a ``functools.partial`` the module is the one of the wrapped function, not ``functools``.
    """
    function = story.function
    while isinstance(function, functools.partial):
        function = function.func
    name = getattr(function, "__module__", None)
    module = sys.modules.get(name) if isinstance(name, str) else None
    return (inspect.getdoc(module) or "") if module is not None else ""


def _siblings(story: Story, registry: StoryRegistry) -> list[Story]:
    """Return the stories of the story's component that are its base or variants of that base, in registration order."""
    base = story.variant_of or story
    return [other for other in registry if other.component == story.component and (other is base or other.variant_of is base)]


__all__ = ["CONTROLS_HEADERS", "NO_CONTROLS_MESSAGE", "NO_SOURCE_MESSAGE", "VARIANT_CAPTION", "DocsPanel", "controls_rows"]
