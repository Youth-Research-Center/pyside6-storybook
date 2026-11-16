"""``Canvas``: the preview scroll area with the controls that change its background and size."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPixmap
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget

from pyside6_storybook.registry import Layout, SizePreset
from pyside6_storybook.registry.size_preset import MAX_SIZE

_MARGIN = 10
_ROW_SPACING = 6
_CONTROL_SPACING = 8
_LABEL_SPACING = 4
_CHECKER_SQUARE = 8
_POPUP_PADDING = 24
_WIDGET_SIZE_LIMIT = 16_777_215
_COMBO_MINIMUM_LENGTH = 7
_SIZE_COMBO_MINIMUM_LENGTH = 7
_DEFAULT_CUSTOM_SIZE = (400, 300)
_FIT = "fit"
_CUSTOM = "custom"
_SIZE_SEPARATOR = " × "
_BUILTIN_SIZES = (
    SizePreset("Phone portrait", 320, 480),
    SizePreset("Phone landscape", 480, 320),
    SizePreset("Dialog", 800, 600),
)
_LAYOUT_ALIGNMENTS = {
    Layout.PADDED: Qt.AlignmentFlag.AlignTop,
    Layout.CENTERED: Qt.AlignmentFlag.AlignCenter,
    Layout.FILL: Qt.AlignmentFlag(0),
}
"""The alignment of the previewed widget inside the surface's margins. An empty alignment lets the widget grow in each direction its
size policy allows; where it cannot grow, the layout centres it."""
_SCROLLABLE_LAYOUTS = frozenset({Layout.PADDED, Layout.CENTERED})


class CanvasBackground(Enum):
    """What the canvas is drawn on; each value is the label in the Background menu."""

    WINDOW = "Window"
    BASE = "Base"
    ALTERNATE_BASE = "Alternate Base"
    CHECKERBOARD = "Checkerboard"


_BACKGROUND_ROLES = {
    CanvasBackground.WINDOW: QPalette.ColorRole.Window,
    CanvasBackground.BASE: QPalette.ColorRole.Base,
    CanvasBackground.ALTERNATE_BASE: QPalette.ColorRole.AlternateBase,
    # The squares are painted over the Window fill, and never through the palette, which would reach the story's widgets.
    CanvasBackground.CHECKERBOARD: QPalette.ColorRole.Window,
}


class _Surface(QFrame):
    """The frame the previewed widget sits in; it paints a checkerboard from its palette when asked to."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._checkerboard = False

    def set_checkerboard(self, *, enabled: bool) -> None:
        """Turn the checkerboard on or off and repaint."""
        if enabled != self._checkerboard:
            self._checkerboard = enabled
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the checkerboard (squares of the palette's Base and Mid) inside the frame when it is on, then the frame."""
        if self._checkerboard:
            area = self.contentsRect()
            palette = self.palette()
            size = _CHECKER_SQUARE
            tile = QPixmap(size * 2, size * 2)
            tile.fill(palette.color(QPalette.ColorRole.Base))
            painter = QPainter(tile)
            painter.fillRect(0, 0, size, size, palette.color(QPalette.ColorRole.Mid))
            painter.fillRect(size, size, size, size, palette.color(QPalette.ColorRole.Mid))
            painter.end()
            painter = QPainter(self)
            painter.drawTiledPixmap(area, tile)
            painter.end()
        super().paintEvent(event)


class Canvas(QWidget):
    """The preview area: a row of controls (background and size) above a scroll area that holds the previewed widget.

    The scroll area is named ``previewScroll`` and the surface inside it ``previewSurface``. With the size "Fit" the surface follows the
    scroll area, as the preview always did. With a size selected, the area inside the surface's margins is exactly that size: the
    surface gets a frame and a fixed size, and the scroll area centres it and scrolls when it does not fit. The choices live on the
    canvas, so they stay when the story, the theme or the registry changes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the canvas with the background "Window" and the size "Fit".

        Args:
            parent: The owning widget.
        """
        super().__init__(parent)
        self.setObjectName("canvas")
        self._placed: QWidget | None = None
        self._layout_kind = Layout.FILL
        self._background = CanvasBackground.WINDOW
        self._shown_size: QSize | None = None

        self._toolbar = QWidget(self)
        self._toolbar.setObjectName("canvasToolbar")
        self._background_combo = self._build_combo("canvasBackground", "Background", _COMBO_MINIMUM_LENGTH)
        for background in CanvasBackground:
            self._background_combo.addItem(background.value, background)
        self._size_combo = self._build_combo("canvasSize", "Size", _SIZE_COMBO_MINIMUM_LENGTH)
        self._width_spin = self._build_spin("canvasWidth", "Width", _DEFAULT_CUSTOM_SIZE[0])
        self._height_spin = self._build_spin("canvasHeight", "Height", _DEFAULT_CUSTOM_SIZE[1])
        self._custom_widgets = (
            self._labelled("Width", self._width_spin),
            self._width_spin,
            self._labelled("Height", self._height_spin),
            self._height_spin,
        )
        self._size_label = QLabel(self._toolbar)
        self._size_label.setObjectName("canvasSizeLabel")
        self._size_label.setAccessibleName("Canvas size")
        self._size_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._size_label.hide()
        self._fill_size_combo(())

        first_row = QHBoxLayout()
        first_row.setSpacing(_CONTROL_SPACING)
        first_row.addLayout(self._pair("Background", self._background_combo))
        first_row.addLayout(self._pair("Size", self._size_combo))
        for widget in self._custom_widgets:
            first_row.addWidget(widget)
        first_row.addStretch(1)
        second_row = QHBoxLayout()
        second_row.setSpacing(_CONTROL_SPACING)
        second_row.addStretch(1)
        second_row.addWidget(self._size_label)
        toolbar_layout = QVBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(_ROW_SPACING)
        toolbar_layout.addLayout(first_row)
        toolbar_layout.addLayout(second_row)
        self._show_custom_controls(visible=False)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("previewScroll")
        self._scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._scroll.setWidgetResizable(True)
        self._scroll.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        self._surface = _Surface(self._scroll)
        self._surface.setObjectName("previewSurface")
        self._surface.setFrameShape(QFrame.Shape.NoFrame)
        # Window, not Base, by default: stories are shown on the background they sit on in an application window, where Fusion's input
        # fields and check boxes (drawn in Base with an outline derived from Window) stand out. On Base they vanish in the Dark theme.
        self._surface.setBackgroundRole(QPalette.ColorRole.Window)
        self._surface.setAutoFillBackground(True)
        self._layout = QVBoxLayout(self._surface)
        self._layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._scroll.setWidget(self._surface)
        self._empty_label = QLabel("", self._surface)
        self._empty_label.setObjectName("previewEmptyState")
        self._empty_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty_label.hide()
        self._layout.addWidget(self._empty_label, alignment=Qt.AlignmentFlag.AlignTop)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, _ROW_SPACING, 0, 0)
        outer.setSpacing(_ROW_SPACING)
        outer.addWidget(self._toolbar)
        outer.addWidget(self._scroll, stretch=1)

        self._background_combo.currentIndexChanged.connect(self._on_background_changed)
        self._size_combo.currentIndexChanged.connect(self._on_size_changed)
        self._width_spin.valueChanged.connect(self._on_custom_size_changed)
        self._height_spin.valueChanged.connect(self._on_custom_size_changed)

    @property
    def surface(self) -> QFrame:
        """The frame a previewed widget must be a child of."""
        return self._surface

    def background(self) -> CanvasBackground:
        """Return the selected background."""
        return self._background

    def active_size(self) -> QSize | None:
        """Return the size of the story's area in pixels, or ``None`` while the size is "Fit"."""
        data = self._size_combo.currentData()
        if data == _FIT:
            return None
        if data == _CUSTOM:
            return QSize(self._width_spin.value(), self._height_spin.value())
        return QSize(data.width, data.height)

    def set_empty_message(self, message: str | None) -> None:
        """Show ``message`` at the top of the surface, or hide the message when it is ``None``."""
        if message is not None:
            self._empty_label.setText(message)
        self._empty_label.setVisible(message is not None)

    def set_size_presets(self, presets: Sequence[SizePreset]) -> None:
        """List ``presets`` in the Size menu after the built-in sizes, keeping the selected size if it is still listed.

        A selected preset that is no longer in the menu returns the size to "Fit". A custom size stays.

        Args:
            presets: The registry's presets, in menu order.
        """
        data = self._size_combo.currentData()
        self._fill_size_combo(presets)
        with QSignalBlocker(self._size_combo):
            if data in (_FIT, _CUSTOM):
                index = self._size_combo.findData(data)
            else:
                index = self._index_of_preset(data)
            self._size_combo.setCurrentIndex(max(index, 0))
        self._apply_size()

    def place(self, widget: QWidget | None, layout: Layout) -> None:
        """Put ``widget`` in the surface for ``layout``, or reset the surface when ``widget`` is ``None``.

        Any widget placed before is removed and deleted. This sets the widget's alignment in the surface, the surface's minimum size and
        the scroll bar policies. In ``PADDED`` and ``CENTERED`` the surface is at least as large as the widget's natural size plus the
        margins, so the preview scrolls instead of squashing the widget. In ``FILL`` there is no minimum and no scroll bar. With a
        size selected the surface has that size, and the scroll bars show when it does not fit.

        Args:
            widget: A child of ``surface``, or ``None`` to reset the surface.
            layout: How to place the widget.
        """
        self.clear()
        self._layout_kind = layout
        self._placed = widget
        if widget is not None:
            self._layout.addWidget(widget)
            self._layout.setAlignment(widget, _LAYOUT_ALIGNMENTS[layout])
        self._apply_geometry()

    def clear(self) -> None:
        """Remove the placed widget, if any, and delete it."""
        widget = self._placed
        self._placed = None
        if widget is not None:
            self._layout.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._layout_kind = Layout.FILL
        self._apply_geometry()

    def _build_combo(self, name: str, accessible_name: str, minimum_length: int) -> QComboBox:
        combo = QComboBox(self._toolbar)
        combo.setObjectName(name)
        combo.setAccessibleName(accessible_name)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(minimum_length)
        return combo

    def _build_spin(self, name: str, accessible_name: str, value: int) -> QSpinBox:
        spin = QSpinBox(self._toolbar)
        spin.setObjectName(name)
        spin.setAccessibleName(accessible_name)
        spin.setRange(1, MAX_SIZE)
        spin.setValue(value)
        spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return spin

    def _labelled(self, text: str, editor: QWidget) -> QLabel:
        label = QLabel(text, self._toolbar)
        label.setBuddy(editor)
        return label

    def _pair(self, text: str, editor: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(_LABEL_SPACING)
        row.addWidget(self._labelled(text, editor))
        row.addWidget(editor)
        return row

    def _show_custom_controls(self, *, visible: bool) -> None:
        for widget in self._custom_widgets:
            widget.setVisible(visible)

    def _fill_size_combo(self, presets: Sequence[SizePreset]) -> None:
        with QSignalBlocker(self._size_combo):
            self._size_combo.clear()
            self._size_combo.addItem("Fit", _FIT)
            for preset in (*_BUILTIN_SIZES, *presets):
                self._size_combo.addItem(f"{preset.name} ({preset.width}{_SIZE_SEPARATOR}{preset.height})", preset)
            self._size_combo.addItem("Custom…", _CUSTOM)

    def _index_of_preset(self, preset: object) -> int:
        for index in range(self._size_combo.count()):
            if isinstance(preset, SizePreset) and self._size_combo.itemData(index) == preset:
                return index
        return -1

    def _on_background_changed(self, index: int) -> None:
        background = self._background_combo.itemData(index)
        if not isinstance(background, CanvasBackground):
            return
        self._background = background
        self._surface.setBackgroundRole(_BACKGROUND_ROLES[background])
        self._surface.set_checkerboard(enabled=background is CanvasBackground.CHECKERBOARD)

    def _on_size_changed(self, _index: int) -> None:
        if self._size_combo.currentData() == _CUSTOM and self._shown_size is not None:
            # Start the custom size at the size that was shown, so choosing Custom does not make the canvas jump.
            with QSignalBlocker(self._width_spin), QSignalBlocker(self._height_spin):
                self._width_spin.setValue(self._shown_size.width())
                self._height_spin.setValue(self._shown_size.height())
        self._apply_size()

    def _on_custom_size_changed(self, _value: int) -> None:
        if self._size_combo.currentData() == _CUSTOM:
            self._apply_size()

    def _apply_size(self) -> None:
        size = self.active_size()
        self._shown_size = size
        self._show_custom_controls(visible=self._size_combo.currentData() == _CUSTOM)
        if size is None:
            self._size_label.hide()
        else:
            self._size_label.setText(f"{size.width()}{_SIZE_SEPARATOR}{size.height()}")
            self._size_label.show()
        self._apply_geometry()

    def _apply_geometry(self) -> None:
        """Set the scroll area's and the surface's sizing for the active size, the layout and the placed widget."""
        size = self.active_size()
        surface = self._surface
        if size is not None:
            surface.setFrameShape(QFrame.Shape.StyledPanel)
            margins = self._layout.contentsMargins()
            frame = 2 * surface.frameWidth()
            self._scroll.setWidgetResizable(False)
            self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            surface.setFixedSize(size.width() + margins.left() + margins.right() + frame, size.height() + margins.top() + margins.bottom() + frame)
            return
        surface.setFrameShape(QFrame.Shape.NoFrame)
        surface.setMaximumSize(_WIDGET_SIZE_LIMIT, _WIDGET_SIZE_LIMIT)
        surface.setMinimumSize(0, 0)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidgetResizable(True)
        scrollable = self._layout_kind in _SCROLLABLE_LAYOUTS
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if scrollable else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        self._scroll.setHorizontalScrollBarPolicy(policy)
        self._scroll.setVerticalScrollBarPolicy(policy)
        widget = self._placed
        if widget is None or not scrollable:
            return
        margins = self._layout.contentsMargins()
        extra = QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        if widget.hasHeightForWidth():
            surface.setMinimumWidth(widget.minimumSizeHint().width() + extra.width())
        else:
            natural = widget.sizeHint().expandedTo(widget.minimumSize()).boundedTo(widget.maximumSize())
            surface.setMinimumSize(natural + extra)


__all__ = ["Canvas", "CanvasBackground"]
