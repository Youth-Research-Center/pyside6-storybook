import pytest
from conftest import show_active
from icon_testing import strongest_pixel
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPalette, QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QScrollArea, QSpinBox, QStackedWidget, QToolButton, QWidget

from pyside6_storybook import Layout, StoryContext, StoryRegistry, TextControl
from pyside6_storybook.gui import canvas as canvas_module
from pyside6_storybook.gui.canvas import PIXEL_BUDGET, ZOOM_LEVELS, Canvas
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemeProvider

pytestmark = pytest.mark.usefixtures("restore_window_activation")

_LINE_X = 10


class _Line(QWidget):
    """A white widget with a one-pixel black vertical line at x = 10."""

    def sizeHint(self) -> QSize:
        return QSize(40, 30)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.fillRect(_LINE_X, 0, 1, self.height(), QColor("#000000"))
        painter.end()


class _Big(QWidget):
    def sizeHint(self) -> QSize:
        return QSize(800, 600)


def _line(ctx: StoryContext) -> QWidget:
    return _Line()


def _big(ctx: StoryContext) -> QWidget:
    return _Big()


def _spin(ctx: StoryContext) -> QWidget:
    spin = QSpinBox()
    spin.setRange(0, 1000)
    spin.setValue(500)
    return spin


def _text(ctx: StoryContext) -> QWidget:
    label = QLabel(str(ctx.args["text"]))
    label.setAutoFillBackground(True)
    label.setBackgroundRole(QPalette.ColorRole.Base)
    return label


def _make_registry() -> StoryRegistry:
    registry = StoryRegistry()
    registry.story("Zoom/Line", layout=Layout.PADDED)(_line)
    registry.story("Zoom/Big", layout=Layout.PADDED)(_big)
    registry.story("Zoom/Spin", layout=Layout.PADDED)(_spin)
    registry.story("Zoom/Text", layout=Layout.PADDED, controls=[TextControl("text", "Hello")])(_text)
    return registry


def _make_window(qtbot, themes: BuiltinThemeProvider, story: str = "Zoom/Line", *, width: int = 1100, height: int = 700) -> GalleryWindow:
    window = GalleryWindow(_make_registry(), themes)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    assert window.select_story(story)
    QApplication.processEvents()
    return window


def _canvas(window: QWidget) -> Canvas:
    canvas = window.findChild(Canvas, "sbkCanvas")
    assert canvas is not None
    return canvas


def _button(window: QWidget, name: str) -> QToolButton:
    button = window.findChild(QToolButton, name)
    assert button is not None
    return button


def _scroll(window: QWidget) -> QScrollArea:
    scroll = window.findChild(QScrollArea, "sbkPreviewScroll")
    assert scroll is not None
    return scroll


def _stack(window: QWidget) -> QStackedWidget:
    stack = window.findChild(QStackedWidget, "sbkPreviewStack")
    assert stack is not None
    return stack


def _image_label(window: QWidget) -> QLabel:
    label = window.findChild(QLabel, "sbkPreviewZoomImage")
    assert label is not None
    return label


def _label(window: QWidget, name: str) -> QLabel:
    label = window.findChild(QLabel, name)
    assert label is not None
    return label


def _ranges(window: QWidget) -> tuple[int, int]:
    scroll = _scroll(window)
    return scroll.horizontalScrollBar().maximum(), scroll.verticalScrollBar().maximum()


def _choose_size(window: QWidget, text: str) -> None:
    combo = window.findChild(QComboBox, "sbkCanvasSize")
    assert combo is not None
    combo.setCurrentIndex(next(i for i in range(combo.count()) if combo.itemText(i).startswith(text)))
    QApplication.processEvents()


def _shown_image(window: QWidget) -> QImage:
    return _image_label(window).pixmap().toImage()


def _wheel(window: QWidget, delta: int, *, ctrl: bool = True, at: QPoint = QPoint(20, 20)) -> None:  # noqa: B008 - QPoint is immutable
    viewport = _scroll(window).viewport()
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event = QWheelEvent(
        QPointF(at),
        QPointF(viewport.mapToGlobal(at)),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,  # noqa: FBT003 - QWheelEvent's inverted flag
    )
    QApplication.sendEvent(viewport, event)
    QApplication.processEvents()


def _wheel_to(widget: QWidget, delta: int, *, ctrl: bool = True) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    centre = widget.rect().center()
    event = QWheelEvent(
        QPointF(centre),
        QPointF(widget.mapToGlobal(centre)),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,  # noqa: FBT003 - QWheelEvent's inverted flag
    )
    QApplication.sendEvent(widget, event)
    QApplication.processEvents()


def _set_custom_size(window: QWidget, width: int, height: int) -> None:
    _choose_size(window, "Custom")
    for name, value in (("sbkCanvasWidth", width), ("sbkCanvasHeight", height)):
        spin = window.findChild(QSpinBox, name)
        assert spin is not None
        spin.setValue(value)
    QApplication.processEvents()


def _record_grabs(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Replace the surface's grab by a recorder of the device pixels it would produce, returning a tiny pixmap."""
    grabbed: list[int] = []

    def grab(self: QWidget) -> QPixmap:
        ratio = self.devicePixelRatio()
        grabbed.append(round(self.width() * self.height() * ratio * ratio))
        return QPixmap(8, 8)

    monkeypatch.setattr(canvas_module._Surface, "grab", grab)
    return grabbed


def test_the_canvas_starts_at_100_percent_with_the_live_surface_shown(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    preview = window.current_preview_widget()
    assert preview is not None

    assert canvas.zoom() == 100
    assert _label(window, "sbkCanvasZoomLevel").text() == "100%"
    stack = _stack(window)
    assert stack.currentIndex() == 0
    assert stack.currentWidget() is canvas.surface
    assert preview.isVisible()
    assert canvas.surface.isAncestorOf(preview)
    assert not _image_label(window).isVisible()
    assert _image_label(window).pixmap().isNull()


def test_each_action_moves_one_level_and_stops_at_the_ends(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    zoom_in = _button(window, "sbkCanvasZoomIn")
    zoom_out = _button(window, "sbkCanvasZoomOut")
    seen = [canvas.zoom()]

    for _ in range(len(ZOOM_LEVELS)):
        if zoom_in.isEnabled():
            qtbot.mouseClick(zoom_in, Qt.MouseButton.LeftButton)
        seen.append(canvas.zoom())
    assert seen == [100, 150, 200, 300, 400, 400, 400, 400]
    assert not zoom_in.isEnabled()
    assert zoom_out.isEnabled()
    assert _label(window, "sbkCanvasZoomLevel").text() == "400%"

    seen = []
    for _ in range(len(ZOOM_LEVELS) + 1):
        if zoom_out.isEnabled():
            qtbot.mouseClick(zoom_out, Qt.MouseButton.LeftButton)
        seen.append(canvas.zoom())
    assert seen == [300, 200, 150, 100, 67, 50, 50, 50]
    assert not zoom_out.isEnabled()
    assert zoom_in.isEnabled()
    assert _label(window, "sbkCanvasZoomLevel").text() == "50%"


def test_the_zoom_buttons_are_accessible_and_have_icons(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)

    expected = {
        "sbkCanvasZoomOut": ("Zoom out", "Ctrl+-"),
        "sbkCanvasZoomIn": ("Zoom in", "Ctrl++"),
        "sbkCanvasZoomReset": ("Reset zoom", "Ctrl+0"),
    }
    for name, (accessible, keys) in expected.items():
        button = _button(window, name)
        assert button.accessibleName() == accessible
        assert keys in button.toolTip()
        assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert not button.icon().isNull()
        assert strongest_pixel(button.icon().pixmap(16, 16)) != QColor(0, 0, 0, 0)


def test_a_standalone_canvas_keeps_its_own_icons(qtbot) -> None:
    canvas = Canvas()
    qtbot.addWidget(canvas)

    button = canvas.findChild(QToolButton, "sbkCanvasZoomIn")
    assert button is not None
    assert not button.icon().isNull()


def test_at_400_percent_a_one_pixel_line_is_four_black_device_pixels_without_blending(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    preview = window.current_preview_widget()
    assert preview is not None

    canvas.set_zoom(400)
    QApplication.processEvents()
    area = preview.geometry()
    image = _shown_image(window)
    ratio = image.devicePixelRatio()
    row = int((area.y() + area.height() // 2) * 4 * ratio)
    first = int(area.x() * 4 * ratio)
    last = int((area.x() + area.width()) * 4 * ratio)
    names = [image.pixelColor(x, row).name() for x in range(first, last)]

    assert set(names) == {"#000000", "#ffffff"}
    assert names.count("#000000") == int(4 * ratio)
    start = first + int(_LINE_X * 4 * ratio)
    assert names[start - first : start - first + int(4 * ratio)] == ["#000000"] * int(4 * ratio)


def test_the_zoom_note_wraps_instead_of_widening_the_canvas(qtbot, themes: BuiltinThemeProvider, restore_application_look: None) -> None:
    # Unwrapped, the note made the canvas wider than its toolbar with the Windows fonts, so zooming grew the window for good.
    font = QApplication.font()
    font.setPointSizeF(font.pointSizeF() * 1.4)
    QApplication.setFont(font)
    window = _make_window(qtbot, themes, "Zoom/Big", width=900, height=600)
    canvas = _canvas(window)
    minimum = canvas.minimumSizeHint().width()

    canvas.set_zoom(300)
    QApplication.processEvents()

    note = window.findChild(QLabel, "sbkCanvasZoomNote")
    assert note is not None
    assert note.isVisible()
    assert canvas.minimumSizeHint().width() == minimum


def test_reset_returns_to_the_live_page_without_a_pixmap_and_with_the_same_scroll_ranges(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Big", width=900, height=600)
    canvas = _canvas(window)
    before = _ranges(window)
    assert before[0] > 0

    canvas.set_zoom(300)
    QApplication.processEvents()
    assert _ranges(window) != before
    qtbot.mouseClick(_button(window, "sbkCanvasZoomReset"), Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert canvas.zoom() == 100
    assert _stack(window).currentIndex() == 0
    assert _image_label(window).pixmap().isNull()
    assert _ranges(window) == before


def test_reset_keeps_sized_canvas_ranges_too(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, width=700, height=500)
    _choose_size(window, "Dialog")
    before = _ranges(window)
    surface_size = _canvas(window).surface.size()

    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    _canvas(window).reset_zoom()
    QApplication.processEvents()

    assert _ranges(window) == before
    assert _canvas(window).surface.size() == surface_size
    assert _stack(window).size() == surface_size


def test_a_control_change_while_zoomed_grabs_again(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Text")
    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    before = _shown_image(window)

    editor = next(child for child in window.findChildren(QLineEdit) if child.text() == "Hello")
    qtbot.keyClicks(editor, " world and more")
    QApplication.processEvents()

    assert _shown_image(window) != before
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "Hello world and more"


def test_a_theme_switch_while_zoomed_grabs_again(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Text")
    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    before = _shown_image(window)

    window.set_theme("Dark" if themes.current_theme() == "Light" else "Light")

    qtbot.waitUntil(lambda: _shown_image(window) != before, timeout=5000)
    label = window.current_preview_widget()
    assert label is not None
    # The label's bottom row, below the baseline of "Hello" (no descenders), so no glyph is sampled; the image is at 200%.
    inside = label.mapTo(_canvas(window).surface, QPoint(label.width() // 2, label.height() - 1)) * 2
    label_color = _shown_image(window).pixelColor(inside)
    assert label_color == _canvas(window).surface.palette().color(QPalette.ColorRole.Base)
    assert _canvas(window).zoom() == 200


def test_a_background_change_while_zoomed_grabs_again(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Text")
    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    before = _shown_image(window)

    combo = window.findChild(QComboBox, "sbkCanvasBackground")
    assert combo is not None
    combo.setCurrentIndex(combo.findText("Base"))
    QApplication.processEvents()

    assert _shown_image(window) != before


def test_ctrl_wheel_zooms_one_level_per_120_units_keeping_the_remainder(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)

    _wheel(window, 60)
    assert canvas.zoom() == 100
    _wheel(window, 60)
    assert canvas.zoom() == 150
    _wheel(window, 360)
    assert canvas.zoom() == 400
    _wheel(window, -120)
    assert canvas.zoom() == 300
    _wheel(window, -60)
    _wheel(window, -60)
    assert canvas.zoom() == 200


def test_the_wheel_without_ctrl_scrolls_and_does_not_zoom(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Big", width=900, height=500)
    canvas = _canvas(window)
    vertical = _scroll(window).verticalScrollBar()
    assert vertical.maximum() > 0

    _wheel(window, -240, ctrl=False)

    assert canvas.zoom() == 100
    assert vertical.value() > 0


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        ((Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier), 150),
        ((Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier), 150),
        ((Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier), 67),
    ],
)
def test_the_zoom_shortcuts_step_one_level_with_focus_in_the_canvas(
    qtbot, themes: BuiltinThemeProvider, keys: tuple[Qt.Key, Qt.KeyboardModifier], expected: int
) -> None:
    window = _make_window(qtbot, themes)
    show_active(qtbot, window)
    combo = window.findChild(QComboBox, "sbkCanvasBackground")
    assert combo is not None
    combo.setFocus()
    qtbot.waitUntil(combo.hasFocus, timeout=5000)

    qtbot.keyClick(combo, keys[0], keys[1])

    assert _canvas(window).zoom() == expected


def test_ctrl_zero_resets_the_zoom(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    show_active(qtbot, window)
    _canvas(window).set_zoom(300)
    button = _button(window, "sbkCanvasZoomIn")
    button.setFocus()
    qtbot.waitUntil(button.hasFocus, timeout=5000)

    qtbot.keyClick(button, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)

    assert _canvas(window).zoom() == 100
    assert _stack(window).currentIndex() == 0


def test_the_zoom_shortcuts_do_nothing_with_focus_outside_the_canvas(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    show_active(qtbot, window)
    target = window.findChild(QLineEdit, "sbkStorySearch")
    assert target is not None
    target.setFocus()
    qtbot.waitUntil(target.hasFocus, timeout=5000)

    qtbot.keyClick(target, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)

    assert _canvas(window).zoom() == 100


def test_the_zoomed_preview_note_is_visible_only_while_zoomed(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    note = _label(window, "sbkCanvasZoomNote")
    canvas = _canvas(window)
    assert not note.isVisible()

    canvas.set_zoom(150)
    assert note.isVisible()
    assert note.text() == "Zoomed previews are images; return to 100% to interact."

    canvas.set_zoom(50)
    assert note.isVisible()
    canvas.reset_zoom()
    assert not note.isVisible()


def test_current_preview_widget_is_the_same_while_zoomed(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    preview = window.current_preview_widget()

    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    assert window.current_preview_widget() is preview

    _canvas(window).reset_zoom()
    QApplication.processEvents()
    assert window.current_preview_widget() is preview
    assert preview is not None
    assert preview.isVisible()


def test_at_50_percent_the_scroll_ranges_follow_the_image_not_the_hidden_surface(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Big", width=900, height=600)
    canvas = _canvas(window)
    live = _ranges(window)
    viewport = _scroll(window).viewport()
    assert live[0] > 0

    canvas.set_zoom(50)
    QApplication.processEvents()
    image = _image_label(window).pixmap()
    logical = QSize(round(image.width() / image.devicePixelRatio()), round(image.height() / image.devicePixelRatio()))

    assert _stack(window).minimumSizeHint().width() <= max(logical.width(), 1) + 1
    assert _ranges(window) == (max(0, logical.width() - viewport.width()), max(0, logical.height() - viewport.height()))
    assert _ranges(window)[0] < live[0]


def test_at_50_percent_a_sized_canvas_follows_the_image(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, width=700, height=500)
    _choose_size(window, "Dialog")
    live = _ranges(window)
    live_width = _canvas(window).surface.width()
    assert live[0] > 0

    _canvas(window).set_zoom(50)
    QApplication.processEvents()

    assert _stack(window).width() == round(live_width / 2)
    assert _ranges(window)[0] < live[0]
    assert _stack(window).currentIndex() == 1


def test_a_fit_mode_resize_while_zoomed_grabs_again_at_the_new_viewport_size(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Text", width=900, height=600)
    _canvas(window).set_zoom(50)
    QApplication.processEvents()
    before = _image_label(window).pixmap().size()

    window.resize(1200, 800)
    qtbot.waitUntil(lambda: _image_label(window).pixmap().size() != before, timeout=5000)

    viewport = _scroll(window).viewport().size()
    ratio = _image_label(window).pixmap().devicePixelRatio()
    assert _image_label(window).pixmap().width() == pytest.approx(viewport.width() * 0.5 * ratio, abs=2)


def test_set_zoom_rejects_a_value_that_is_not_a_level(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)

    with pytest.raises(ValueError, match="not a zoom level"):
        _canvas(window).set_zoom(120)

    assert _canvas(window).zoom() == 100


def test_the_zoom_stays_when_the_story_changes_and_is_grabbed_for_the_new_story(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    before = _shown_image(window)

    assert window.select_story("Zoom/Text")
    QApplication.processEvents()

    assert _canvas(window).zoom() == 200
    assert _shown_image(window) != before


class _Fixed(QWidget):
    def sizeHint(self) -> QSize:
        return QSize(200, 100)


def _centered(ctx: StoryContext) -> QWidget:
    return _Fixed()


def _anchor_window(qtbot, themes: BuiltinThemeProvider) -> GalleryWindow:
    registry = StoryRegistry()
    registry.story("Zoom/Centered", layout=Layout.CENTERED)(_centered)
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    return window


def test_zooming_keeps_a_centred_widget_in_view(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _anchor_window(qtbot, themes)
    preview = window.current_preview_widget()
    assert preview is not None
    centre = preview.geometry().center()

    _canvas(window).set_zoom(300)
    QApplication.processEvents()

    viewport = _scroll(window).viewport()
    on_viewport = _stack(window).mapTo(viewport, QPoint(centre.x() * 3, centre.y() * 3))
    assert viewport.rect().contains(on_viewport)
    assert _scroll(window).horizontalScrollBar().maximum() > 0


def test_zooming_in_then_out_returns_to_the_same_scroll_values(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    _choose_size(window, "Custom")
    for name, value in (("sbkCanvasWidth", 1600), ("sbkCanvasHeight", 1200)):
        spin = window.findChild(QSpinBox, name)
        assert spin is not None
        spin.setValue(value)
    QApplication.processEvents()
    horizontal = _scroll(window).horizontalScrollBar()
    vertical = _scroll(window).verticalScrollBar()
    horizontal.setValue(150)
    vertical.setValue(120)
    start = (horizontal.value(), vertical.value())
    assert start == (150, 120)

    _canvas(window).set_zoom(200)
    QApplication.processEvents()
    assert (horizontal.value(), vertical.value()) != start
    _canvas(window).set_zoom(100)
    QApplication.processEvents()

    assert abs(horizontal.value() - start[0]) <= 1
    assert abs(vertical.value() - start[1]) <= 1


def test_ctrl_wheel_keeps_the_content_under_the_cursor(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, width=700, height=500)
    _choose_size(window, "Dialog")
    viewport = _scroll(window).viewport()
    cursor = QPoint(100, 80)
    before = _stack(window).mapFrom(viewport, cursor)

    _wheel(window, 120, at=cursor)

    assert _canvas(window).zoom() == 150
    after = _stack(window).mapTo(viewport, QPoint(round(before.x() * 1.5), round(before.y() * 1.5)))
    assert abs(after.x() - cursor.x()) <= 2
    assert abs(after.y() - cursor.y()) <= 2


def test_a_zoom_level_beyond_the_pixel_budget_is_not_reachable(qtbot, themes: BuiltinThemeProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    grabbed = _record_grabs(monkeypatch)
    _set_custom_size(window, 10_000, 10_000)

    canvas.set_zoom(400)
    canvas.zoom_in()
    _wheel(window, 240)

    assert canvas.zoom() == 100
    assert not _button(window, "sbkCanvasZoomIn").isEnabled()
    assert not _button(window, "sbkCanvasZoomOut").isEnabled()
    assert all(pixels <= PIXEL_BUDGET for pixels in grabbed)


def test_zoom_in_stops_at_the_last_level_within_the_budget(qtbot, themes: BuiltinThemeProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    grabbed = _record_grabs(monkeypatch)
    _set_custom_size(window, 5_000, 5_000)

    canvas.set_zoom(400)
    assert canvas.zoom() == 150
    canvas.reset_zoom()
    canvas.zoom_in()
    assert canvas.zoom() == 150
    canvas.zoom_in()

    assert canvas.zoom() == 150
    assert not _button(window, "sbkCanvasZoomIn").isEnabled()
    assert _button(window, "sbkCanvasZoomOut").isEnabled()
    assert grabbed
    assert all(pixels * (max(canvas.zoom(), 100) / 100) ** 2 <= PIXEL_BUDGET for pixels in grabbed)


def test_a_size_change_lowers_a_zoom_the_new_size_cannot_afford(qtbot, themes: BuiltinThemeProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(qtbot, themes)
    canvas = _canvas(window)
    grabbed = _record_grabs(monkeypatch)
    _set_custom_size(window, 400, 300)
    canvas.set_zoom(400)
    assert canvas.zoom() == 400

    _set_custom_size(window, 5_000, 5_000)

    assert canvas.zoom() == 150
    assert _label(window, "sbkCanvasZoomLevel").text() == "150%"
    assert all(pixels * 2.25 <= PIXEL_BUDGET for pixels in grabbed[-1:])


def test_ctrl_wheel_over_a_story_widget_zooms_and_does_not_reach_it(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Spin")
    canvas = _canvas(window)
    spin = window.current_preview_widget()
    assert isinstance(spin, QSpinBox)

    _wheel_to(spin, 120)

    assert canvas.zoom() == 150
    assert spin.value() == 500


def test_the_wheel_over_unrelated_widgets_is_left_alone(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Spin")
    canvas = _canvas(window)
    other = QSpinBox()
    qtbot.addWidget(other)
    other.setRange(0, 1000)
    other.setValue(500)
    other.show()
    qtbot.waitExposed(other)

    _wheel_to(other, 120, ctrl=False)
    assert other.value() != 500
    value = other.value()
    _wheel_to(other, 120)

    assert canvas.zoom() == 100
    assert other.value() != value
    spin = window.current_preview_widget()
    assert isinstance(spin, QSpinBox)
    _wheel_to(spin, 120, ctrl=False)
    assert canvas.zoom() == 100
    assert spin.value() != 500


def test_a_hidden_canvas_stops_watching_the_wheel(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Spin")
    canvas = _canvas(window)
    spin = window.current_preview_widget()
    assert isinstance(spin, QSpinBox)
    window.hide()

    _wheel_to(spin, 120)

    assert canvas.zoom() == 100


def test_a_deleted_canvas_leaves_no_filter_behind(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, "Zoom/Spin")
    other = QSpinBox()
    qtbot.addWidget(other)
    other.setRange(0, 1000)
    other.show()
    qtbot.waitExposed(other)
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    with qtbot.capture_exceptions() as exceptions:
        _wheel_to(other, 120)

    assert exceptions == []
