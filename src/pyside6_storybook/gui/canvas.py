"""``Canvas``: the preview scroll area with the controls that change its background and size."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPainter, QPaintEvent, QPalette, QPixmap, QShortcut, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.gui.icons import ActionIcons
from pyside6_storybook.registry import Layout, SizePreset

_MARGIN = 10
_ROW_SPACING = 6
_CONTROL_SPACING = 8
_LABEL_SPACING = 4
_CHECKER_SQUARE = 8
_POPUP_PADDING = 24
_MAX_SIZE = 10_000
_WIDGET_SIZE_LIMIT = 16_777_215
_COMBO_MINIMUM_LENGTH = 7
_SIZE_COMBO_MINIMUM_LENGTH = 7
_DEFAULT_CUSTOM_SIZE = (400, 300)
ZOOM_LEVELS = (50, 67, 100, 150, 200, 300, 400)
"""The zoom levels in percent, in the order the zoom buttons step through them."""
_DEFAULT_ZOOM = 100
_WHEEL_STEP = 120
_ZOOM_NOTE = "Zoomed previews are images; return to 100% to interact."
_LIVE_PAGE = 0
_ZOOM_PAGE = 1
_ZOOM_SHORTCUTS = {"Ctrl++": "in", "Ctrl+=": "in", "Ctrl+-": "out", "Ctrl+0": "reset"}
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

    The scroll area's widget is a ``QStackedWidget`` named ``previewStack``: page 0 is the live surface and page 1 a label. At 100% the
    surface is shown as it is. At any other zoom level the canvas grabs the surface, scales the image without smoothing and shows it
    on the label, so a zoomed preview is not interactive.
    """

    def __init__(self, parent: QWidget | None = None, *, icons: ActionIcons | None = None) -> None:
        """Create the canvas with the background "Window", the size "Fit" and the zoom 100%.

        Args:
            parent: The owning widget.
            icons: The registry that tints the zoom buttons' icons. When omitted, the canvas keeps its own and renders the icons
                again when its palette changes.
        """
        super().__init__(parent)
        self.setObjectName("canvas")
        self._owns_icons = icons is None
        self._icons = ActionIcons() if icons is None else icons
        self._zoom = _DEFAULT_ZOOM
        self._wheel_remainder = 0
        self._sized_surface: QSize | None = None
        self._grab_viewport = QSize()
        self._regrab_timer = QTimer(self)
        self._regrab_timer.setSingleShot(True)
        self._regrab_timer.setInterval(0)
        self._regrab_timer.timeout.connect(self._refresh_zoom)
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
        self._zoom_out_button = self._build_zoom_button("canvasZoomOut", "Zoom out", "Zoom out (Ctrl+-)", "magnifying-glass-minus")
        self._zoom_level_label = QLabel(self._toolbar)
        self._zoom_level_label.setObjectName("canvasZoomLevel")
        self._zoom_level_label.setAccessibleName("Zoom level")
        self._zoom_in_button = self._build_zoom_button("canvasZoomIn", "Zoom in", "Zoom in (Ctrl++)", "magnifying-glass-plus")
        self._zoom_reset_button = self._build_zoom_button("canvasZoomReset", "Reset zoom", "Reset zoom to 100% (Ctrl+0)", "arrow-counter-clockwise")
        second_row = QHBoxLayout()
        second_row.setSpacing(_CONTROL_SPACING)
        second_row.addWidget(self._zoom_out_button)
        second_row.addWidget(self._zoom_level_label)
        second_row.addWidget(self._zoom_in_button)
        second_row.addWidget(self._zoom_reset_button)
        second_row.addStretch(1)
        second_row.addWidget(self._size_label)
        toolbar_layout = QVBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(_ROW_SPACING)
        toolbar_layout.addLayout(first_row)
        toolbar_layout.addLayout(second_row)
        self._show_custom_controls(visible=False)

        self._zoom_note = QLabel(_ZOOM_NOTE, self)
        self._zoom_note.setObjectName("canvasZoomNote")
        self._zoom_note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._zoom_note.hide()

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("previewScroll")
        self._scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._scroll.setWidgetResizable(True)
        self._scroll.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        self._stack = QStackedWidget(self._scroll)
        self._stack.setObjectName("previewStack")
        self._surface = _Surface(self._stack)
        self._surface.setObjectName("previewSurface")
        self._surface.setFrameShape(QFrame.Shape.NoFrame)
        # Window, not Base, by default: stories are shown on the background they sit on in an application window, where Fusion's input
        # fields and check boxes (drawn in Base with an outline derived from Window) stand out. On Base they vanish in the Dark theme.
        self._surface.setBackgroundRole(QPalette.ColorRole.Window)
        self._surface.setAutoFillBackground(True)
        self._layout = QVBoxLayout(self._surface)
        self._layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._surface_policy = self._surface.sizePolicy()
        self._zoom_label = QLabel(self._stack)
        self._zoom_label.setObjectName("previewZoomImage")
        self._zoom_label.setFrameShape(QFrame.Shape.NoFrame)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._zoom_label.setAccessibleName("Zoomed preview")
        self._stack.insertWidget(_LIVE_PAGE, self._surface)
        self._stack.insertWidget(_ZOOM_PAGE, self._zoom_label)
        self._scroll.setWidget(self._stack)
        self._empty_label = QLabel("", self._surface)
        self._empty_label.setObjectName("previewEmptyState")
        self._empty_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty_label.hide()
        self._layout.addWidget(self._empty_label, alignment=Qt.AlignmentFlag.AlignTop)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, _ROW_SPACING, 0, 0)
        outer.setSpacing(_ROW_SPACING)
        outer.addWidget(self._toolbar)
        outer.addWidget(self._zoom_note)
        outer.addWidget(self._scroll, stretch=1)

        self._background_combo.currentIndexChanged.connect(self._on_background_changed)
        self._size_combo.currentIndexChanged.connect(self._on_size_changed)
        self._width_spin.valueChanged.connect(self._on_custom_size_changed)
        self._height_spin.valueChanged.connect(self._on_custom_size_changed)
        self._zoom_out_button.clicked.connect(self.zoom_out)
        self._zoom_in_button.clicked.connect(self.zoom_in)
        self._zoom_reset_button.clicked.connect(self.reset_zoom)
        self._shortcuts = [self._build_shortcut(keys, action) for keys, action in _ZOOM_SHORTCUTS.items()]
        self._scroll.viewport().installEventFilter(self)
        self._update_zoom_controls()

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

    def zoom(self) -> int:
        """Return the zoom level in percent, one of ``ZOOM_LEVELS``."""
        return self._zoom

    def set_zoom(self, percent: int) -> None:
        """Show the preview at a zoom level.

        Args:
            percent: One of ``ZOOM_LEVELS``.

        Raises:
            ValueError: If ``percent`` is not a zoom level.
        """
        if percent not in ZOOM_LEVELS:
            message = f"{percent} is not a zoom level; the levels are {ZOOM_LEVELS}."
            raise ValueError(message)
        if percent != self._zoom:
            self._zoom = percent
            self._apply_geometry()

    def zoom_in(self) -> None:
        """Step to the next zoom level; nothing happens at the largest."""
        self._step_zoom(1)

    def zoom_out(self) -> None:
        """Step to the previous zoom level; nothing happens at the smallest."""
        self._step_zoom(-1)

    def reset_zoom(self) -> None:
        """Return to 100%, where the live preview is shown."""
        self.set_zoom(_DEFAULT_ZOOM)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Zoom on Ctrl+wheel over the preview, and grab the surface again when the viewport is resized in Fit mode while zoomed."""
        if watched is self._scroll.viewport():
            if event.type() == QEvent.Type.Wheel and isinstance(event, QWheelEvent) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._wheel_remainder += event.angleDelta().y()
                steps = int(self._wheel_remainder / _WHEEL_STEP)
                self._wheel_remainder -= steps * _WHEEL_STEP
                self._step_zoom(steps)
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.Resize
                and self._zoom != _DEFAULT_ZOOM
                and self.active_size() is None
                and self._scroll.viewport().size() != self._grab_viewport
            ):
                self._refresh_zoom()
        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent) -> None:
        """On a palette change, render the icons again if the canvas keeps them, and grab the surface again while zoomed."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            if self._owns_icons:
                self._icons.retint(self.palette())
            if self._zoom != _DEFAULT_ZOOM:
                # The children get the palette after this widget does, so the grab waits for the event loop.
                self._regrab_timer.start()

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

    def _build_zoom_button(self, name: str, accessible_name: str, tooltip: str, icon: str) -> QToolButton:
        button = QToolButton(self._toolbar)
        button.setObjectName(name)
        button.setAccessibleName(accessible_name)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._icons.bind(button, icon)
        return button

    def _build_shortcut(self, keys: str, action: str) -> QShortcut:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        handlers = {"in": self.zoom_in, "out": self.zoom_out, "reset": self.reset_zoom}
        shortcut.activated.connect(handlers[action])
        return shortcut

    def _step_zoom(self, steps: int) -> None:
        index = ZOOM_LEVELS.index(self._zoom) + steps
        self.set_zoom(ZOOM_LEVELS[max(0, min(index, len(ZOOM_LEVELS) - 1))])

    def _update_zoom_controls(self) -> None:
        self._zoom_level_label.setText(f"{self._zoom}%")
        self._zoom_out_button.setEnabled(self._zoom > ZOOM_LEVELS[0])
        self._zoom_in_button.setEnabled(self._zoom < ZOOM_LEVELS[-1])
        self._zoom_note.setVisible(self._zoom != _DEFAULT_ZOOM)

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
        spin.setRange(1, _MAX_SIZE)
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
        self._refresh_zoom()

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
        """Set the sizing of the surface, the stack and the scroll area for the active size, the layout and the zoom, then refresh the zoom."""
        self._constrain_surface()
        self._refresh_zoom()

    def _constrain_surface(self) -> None:
        """Set the surface's frame and size limits for the active size, the layout and the placed widget."""
        size = self.active_size()
        surface = self._surface
        if size is not None:
            surface.setFrameShape(QFrame.Shape.StyledPanel)
            margins = self._layout.contentsMargins()
            frame = 2 * surface.frameWidth()
            width = size.width() + margins.left() + margins.right() + frame
            height = size.height() + margins.top() + margins.bottom() + frame
            self._sized_surface = QSize(width, height)
            surface.setFixedSize(self._sized_surface)
            return
        self._sized_surface = None
        surface.setFrameShape(QFrame.Shape.NoFrame)
        surface.setMaximumSize(_WIDGET_SIZE_LIMIT, _WIDGET_SIZE_LIMIT)
        surface.setMinimumSize(0, 0)
        widget = self._placed
        if widget is None or self._layout_kind not in _SCROLLABLE_LAYOUTS:
            return
        margins = self._layout.contentsMargins()
        extra = QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        if widget.hasHeightForWidth():
            surface.setMinimumWidth(widget.minimumSizeHint().width() + extra.width())
        else:
            natural = widget.sizeHint().expandedTo(widget.minimumSize()).boundedTo(widget.maximumSize())
            surface.setMinimumSize(natural + extra)

    def _refresh_zoom(self) -> None:
        """Show the live surface at 100%, or grab it and show the scaled image at another level."""
        self._update_zoom_controls()
        if self._zoom == _DEFAULT_ZOOM:
            # The pixmap goes first: it would keep the stack's minimum size large, and the live preview would get scroll bars.
            self._zoom_label.clear()
            self._surface.setSizePolicy(self._surface_policy)
            self._constrain_surface()
            self._set_stack_size(None)
            self._stack.setCurrentIndex(_LIVE_PAGE)
            self._apply_scrolling()
            return
        surface = self._surface
        self._constrain_surface()
        surface.ensurePolished()
        viewport = self._scroll.viewport().size()
        self._grab_viewport = viewport
        if self._sized_surface is None:
            surface.resize(viewport)
        self._layout.activate()
        pixmap = surface.grab()
        ratio = pixmap.devicePixelRatio()
        factor = self._zoom / 100
        target = QSize(max(1, round(pixmap.width() * factor)), max(1, round(pixmap.height() * factor)))
        scaled = pixmap.scaled(target, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        scaled.setDevicePixelRatio(ratio)
        # A hidden surface must not hold the stack at its live size, so the scroll ranges follow the image.
        surface.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        surface.setMinimumSize(0, 0)
        surface.setMaximumSize(_WIDGET_SIZE_LIMIT, _WIDGET_SIZE_LIMIT)
        self._zoom_label.setPixmap(scaled)
        self._set_stack_size(QSize(math.ceil(scaled.width() / ratio), math.ceil(scaled.height() / ratio)))
        self._stack.setCurrentIndex(_ZOOM_PAGE)
        self._apply_scrolling()

    def _set_stack_size(self, image: QSize | None) -> None:
        """Fix the stack at the live surface's size or the image's size when a size is selected, and leave it free in Fit mode."""
        if self.active_size() is None:
            self._stack.setMinimumSize(0, 0)
            self._stack.setMaximumSize(_WIDGET_SIZE_LIMIT, _WIDGET_SIZE_LIMIT)
        else:
            fixed = image if image is not None else self._sized_surface
            if fixed is not None:
                self._stack.setFixedSize(fixed)

    def _apply_scrolling(self) -> None:
        """Set how the scroll area sizes and aligns the stack and when its scroll bars show."""
        zoomed = self._zoom != _DEFAULT_ZOOM
        if self.active_size() is not None:
            self._scroll.setWidgetResizable(False)
            self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            return
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidgetResizable(True)
        scrollable = zoomed or self._layout_kind in _SCROLLABLE_LAYOUTS
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if scrollable else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        self._scroll.setHorizontalScrollBarPolicy(policy)
        self._scroll.setVerticalScrollBarPolicy(policy)


__all__ = ["ZOOM_LEVELS", "Canvas", "CanvasBackground"]
