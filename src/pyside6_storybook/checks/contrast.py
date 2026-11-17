"""``check_text_contrast``: whether the text of a widget tree is readable against what is drawn behind it, measured on the pixels."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont, QFontMetrics, QImage, QPalette, QTextDocument
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QRadioButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QTableView,
    QTreeView,
    QWidget,
)

from pyside6_storybook.checks._tree import is_internal, make_issue
from pyside6_storybook.checks.check_issue import CheckIssue
from pyside6_storybook.checks.rules import RULE_CONTRAST
from pyside6_storybook.contrast import contrast_ratio

DEFAULT_NORMAL = 4.5
"""The WCAG AA ratio for normal text."""

DEFAULT_LARGE = 3.0
"""The WCAG AA ratio for large text."""

_MAX_ITEMS_PER_VIEW = 50
"""How many items of an item view are checked."""

_MIN_PIXELS = 3
"""A colour is text only when it covers at least this many pixels of the text's box."""

_LARGE_POINTS = 18.0
_LARGE_BOLD_POINTS = 14.0
_MAX_SCANNED_INDEXES = 2000
"""How many model indexes of one view are looked at while searching for the visible ones."""

_MARKUP = re.compile(r"<[a-zA-Z/!]")
"""Text that an auto-format label shows as rich text: it has a tag or a comment."""

_TEXT_FLAGS = int(Qt.TextFlag.TextShowMnemonic.value)
_LEFT_VCENTER = int(Qt.AlignmentFlag.AlignLeft.value | Qt.AlignmentFlag.AlignVCenter.value)
_ITEM_PADDING = 3
"""The horizontal space the style leaves around the text of an item, in pixels."""


@dataclass(frozen=True, slots=True)
class _TextBox:
    """Text to measure: where its container is, how it is aligned and which font draws it."""

    widget: QWidget
    container: QRect
    """In the coordinates of ``widget``."""
    text: str
    flags: int
    font: QFont
    what: str = ""
    """Names a part of the widget (``"item (row 1, column 2)"``) or is empty."""


def check_text_contrast(
    widget: QWidget, *, normal: float = DEFAULT_NORMAL, large: float = DEFAULT_LARGE, include_disabled: bool = False
) -> list[CheckIssue]:
    """Find the text in ``widget`` that is too faint against its background, measured on the pixels that are drawn.

    ``widget`` should be shown, and its focus cleared, because the check renders it once with ``QWidget.render`` into an image and
    measures that. Pixels, not palette roles, so a widget styled by a style sheet or painted by hand is measured as it looks. For each
    visible text-bearing descendant (and the widget itself) the check takes the text's own box inside its container, finds the most
    frequent colour there (the background) and, among the colours that cover at least 3 pixels, the one with the highest contrast ratio
    against it (the text). A box that holds only one colour fails: the text is drawn in the background colour, or not at all.

    The text of labels (without a pixmap), buttons, line edits, spin boxes and combo boxes is checked, and up to 50 visible items of
    each list, table and tree. Large text (at least 18 pt, or at least 14 pt and bold) needs ``large``, other text ``normal``.
    Progress-bar text, group box titles, header text, placeholder text and text that a widget paints itself are not checked, and
    text on a gradient or an image, or very thin text, gives an estimate.

    Args:
        widget: The widget to check, with everything in it.
        normal: The contrast ratio that normal text needs. WCAG AA asks for 4.5.
        large: The contrast ratio that large text needs. WCAG AA asks for 3.
        include_disabled: Whether disabled widgets are checked too; their text is faint by design, so they are skipped by default.

    Returns:
        The issues, in the order the widgets are found; empty when every text passes. An issue names the widget, the two colours as
        ``#rrggbb``, the measured ratio, the threshold and whether the text is large.
    """
    image = _render(widget)
    issues: list[CheckIssue] = []
    for box in _text_boxes(widget, include_disabled=include_disabled):
        message = _measure(widget, image, box, normal=normal, large=large)
        if message is not None:
            issues.append(make_issue(RULE_CONTRAST, widget, box.widget, message))
    return issues


def _render(widget: QWidget) -> QImage:
    """Return what ``widget`` looks like, as an image of device pixel ratio 1.

    The whole window is rendered and ``widget`` is cut out of it, so a translucent background is blended over what is behind it
    as it is on the screen, and not drawn opaque.
    """
    window = widget.window()
    image = QImage(window.size(), QImage.Format.Format_RGB32)
    image.setDevicePixelRatio(1.0)
    image.fill(window.palette().color(QPalette.ColorRole.Window))
    window.render(image)
    return image.copy(QRect(widget.mapTo(window, QPoint(0, 0)), widget.size()))


def _measure(root: QWidget, image: QImage, box: _TextBox, *, normal: float, large: float) -> str | None:
    """Return the failure message for ``box``, or ``None`` when it passes or has nothing to measure."""
    rectangle = _text_rectangle(root, box)
    if rectangle is None:
        return None
    counts = _colour_counts(image.copy(rectangle))
    if not counts:
        return None
    background = counts.most_common(1)[0][0]
    is_large = _is_large(box.font, box.widget)
    threshold = large if is_large else normal
    kind = "large" if is_large else "normal"
    subject = f"{box.what + ' ' if box.what else ''}text {box.text[:40]!r}"
    candidates = [colour for colour, count in counts.items() if colour != background and count >= _MIN_PIXELS]
    if not candidates:
        candidates = [colour for colour in counts if colour != background]
    if not candidates:
        return f"{subject} is drawn in the background colour {_hex(background)} or not drawn at all; its contrast is 1.00:1 (needs {threshold:g}:1)"
    best = max(candidates, key=lambda colour: contrast_ratio(_hex(colour), _hex(background)))
    ratio = contrast_ratio(_hex(best), _hex(background))
    if ratio >= threshold:
        return None
    return f"{subject} is {_hex(best)} on {_hex(background)}, a contrast of {ratio:.2f}:1; {kind} text needs {threshold:g}:1"


def _text_rectangle(root: QWidget, box: _TextBox) -> QRect | None:
    """Return the text's box in the coordinates of the root's image, or ``None`` when it is empty or not all visible."""
    container = box.container
    if container.isEmpty():
        return None
    rectangle = QFontMetrics(box.font).boundingRect(container, box.flags, box.text).adjusted(-1, -1, 1, 1).intersected(container)
    size = rectangle.size()
    rectangle = rectangle.intersected(box.widget.rect())
    current = box.widget
    while current is not root:
        parent = current.parentWidget()
        if parent is None:
            return None
        rectangle = rectangle.translated(current.pos()).intersected(parent.rect())
        current = parent
    rectangle = rectangle.intersected(root.rect())
    # Text that a scroll area or the window cuts off is not drawn in full, so what is left of it says nothing about its colour.
    return None if rectangle.size() != size else rectangle


def _colour_counts(image: QImage) -> Counter[int]:
    """Count the pixels of each colour (``0xRRGGBB``) in an image."""
    converted = image.convertToFormat(QImage.Format.Format_RGB32)
    data = memoryview(bytes(converted.constBits())).cast("I")
    width, height, stride = converted.width(), converted.height(), converted.bytesPerLine() // 4
    counts: Counter[int] = Counter()
    for row in range(height):
        counts.update(pixel & 0xFFFFFF for pixel in data[row * stride : row * stride + width])
    return counts


def _hex(colour: int) -> str:
    return f"#{colour:06x}"


def _is_large(font: QFont, widget: QWidget) -> bool:
    points = font.pointSizeF()
    if points <= 0:
        points = font.pixelSize() * 72.0 / max(widget.logicalDpiY(), 1)
    bold = font.weight().value >= QFont.Weight.Bold.value
    return points >= _LARGE_POINTS or (points >= _LARGE_BOLD_POINTS and bold)


def _text_boxes(root: QWidget, *, include_disabled: bool) -> Iterator[_TextBox]:
    for candidate in [root, *root.findChildren(QWidget)]:
        if candidate.window() is not root.window() or not candidate.isVisibleTo(root) or is_internal(candidate):
            continue
        if not include_disabled and not candidate.isEnabled():
            continue
        yield from _boxes_of(candidate)


def _boxes_of(widget: QWidget) -> Iterator[_TextBox]:
    if isinstance(widget, QLabel):
        yield from _label_boxes(widget)
    elif isinstance(widget, QAbstractButton):
        yield from _button_boxes(widget)
    elif isinstance(widget, QLineEdit):
        if widget.displayText():
            yield _TextBox(widget, widget.contentsRect(), widget.displayText(), _LEFT_VCENTER, widget.font())
    elif isinstance(widget, QAbstractSpinBox):
        yield from _spin_box_boxes(widget)
    elif isinstance(widget, QComboBox):
        yield from _combo_box_boxes(widget)
    elif isinstance(widget, QAbstractItemView):
        yield from _item_boxes(widget)


def _label_boxes(label: QLabel) -> Iterator[_TextBox]:
    if not label.text() or not label.pixmap().isNull() or label.movie() is not None:
        return
    text = label.text()
    if label.textFormat() == Qt.TextFormat.RichText or (label.textFormat() == Qt.TextFormat.AutoText and _MARKUP.search(text) is not None):
        document = QTextDocument()
        document.setHtml(text)
        text = document.toPlainText()
    margin = label.margin()
    flags = int(label.alignment().value) | _TEXT_FLAGS | (int(Qt.TextFlag.TextWordWrap.value) if label.wordWrap() else 0)
    if text.strip():
        yield _TextBox(label, label.contentsRect().adjusted(margin, margin, -margin, -margin), text, flags, label.font())


def _button_boxes(button: QAbstractButton) -> Iterator[_TextBox]:
    text = button.text()
    if not text.strip():
        return
    option = QStyleOptionButton()
    option.initFrom(button)
    option.text = text
    option.icon = button.icon()
    option.iconSize = button.iconSize()
    style = button.style()
    if isinstance(button, QPushButton):
        container = style.subElementRect(QStyle.SubElement.SE_PushButtonContents, option, button)
        flags = int(Qt.AlignmentFlag.AlignCenter.value)
    elif isinstance(button, QCheckBox):
        container = style.subElementRect(QStyle.SubElement.SE_CheckBoxContents, option, button)
        flags = _LEFT_VCENTER
    elif isinstance(button, QRadioButton):
        container = style.subElementRect(QStyle.SubElement.SE_RadioButtonContents, option, button)
        flags = _LEFT_VCENTER
    else:
        container = button.contentsRect()
        flags = int(Qt.AlignmentFlag.AlignCenter.value)
    yield _TextBox(button, container, text, flags | _TEXT_FLAGS, button.font())


def _spin_box_boxes(spin_box: QAbstractSpinBox) -> Iterator[_TextBox]:
    text = spin_box.lineEdit().displayText() if spin_box.lineEdit() is not None else ""
    if not text:
        return
    option = QStyleOptionSpinBox()
    option.initFrom(spin_box)
    option.buttonSymbols = spin_box.buttonSymbols()
    option.subControls = QStyle.SubControl.SC_All
    container = spin_box.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxEditField, spin_box)
    yield _TextBox(spin_box, container, text, int(spin_box.alignment().value), spin_box.font())


def _combo_box_boxes(combo_box: QComboBox) -> Iterator[_TextBox]:
    editor = combo_box.lineEdit()
    text = editor.displayText() if editor is not None else combo_box.currentText()
    if not text:
        return
    option = QStyleOptionComboBox()
    option.initFrom(combo_box)
    option.editable = combo_box.isEditable()
    option.subControls = QStyle.SubControl.SC_All
    container = combo_box.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxEditField, combo_box)
    yield _TextBox(combo_box, container, text, _LEFT_VCENTER, combo_box.font())


def _item_boxes(view: QAbstractItemView) -> Iterator[_TextBox]:
    viewport = view.viewport()
    count = 0
    for index in _visible_indexes(view):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is None or not str(text).strip():
            continue
        rectangle = view.visualRect(index).intersected(viewport.rect())
        if rectangle.isEmpty():
            continue
        font = index.data(Qt.ItemDataRole.FontRole)
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        left = _ITEM_PADDING
        if index.data(Qt.ItemDataRole.DecorationRole) is not None:
            left += view.iconSize().width() + _ITEM_PADDING
        container = view.visualRect(index).adjusted(left, 0, -_ITEM_PADDING, 0)
        flags = (int(alignment) if alignment is not None else _LEFT_VCENTER) | _TEXT_FLAGS
        what = f"item (row {index.row()}, column {index.column()})"
        yield _TextBox(viewport, container, str(text), flags, font if isinstance(font, QFont) else view.font(), what)
        count += 1
        if count >= _MAX_ITEMS_PER_VIEW:
            return


def _visible_indexes(view: QAbstractItemView) -> Iterator:
    """Yield model indexes of ``view`` that are probably visible, starting from the top left, looking at a bounded number of them."""
    model = view.model()
    if model is None:
        return
    viewport = view.viewport()
    if isinstance(view, QTableView):
        first_row, first_column = max(view.rowAt(0), 0), max(view.columnAt(0), 0)
        last_row = view.rowAt(viewport.height() - 1)
        last_column = view.columnAt(viewport.width() - 1)
        last_row = model.rowCount() - 1 if last_row < 0 else last_row
        last_column = model.columnCount() - 1 if last_column < 0 else last_column
        scanned = 0
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                scanned += 1
                if scanned > _MAX_SCANNED_INDEXES:
                    return
                yield model.index(row, column)
    elif isinstance(view, QTreeView):
        index = view.indexAt(QPoint(0, 0))
        for _ in range(_MAX_SCANNED_INDEXES):
            if not index.isValid():
                return
            yield from (index.siblingAtColumn(column) for column in range(model.columnCount(index.parent())))
            index = view.indexBelow(index)
    elif isinstance(view, QListView):
        start = max(view.indexAt(QPoint(0, 0)).row(), 0)
        for row in range(start, min(model.rowCount(view.rootIndex()), start + _MAX_SCANNED_INDEXES)):
            yield model.index(row, view.modelColumn(), view.rootIndex())


__all__ = ["DEFAULT_LARGE", "DEFAULT_NORMAL", "check_text_contrast"]
