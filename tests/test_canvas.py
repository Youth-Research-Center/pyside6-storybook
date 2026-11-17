import functools

import pytest
from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QLabel, QScrollArea, QSizePolicy, QSpinBox, QWidget

from pyside6_storybook import Layout, SizePreset, StoryContext, StoryRegistry
from pyside6_storybook.gui.canvas import Canvas, CanvasBackground
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemeProvider

_BUILTIN_SIZES = {"Phone portrait": (320, 480), "Phone landscape": (480, 320), "Dialog": (800, 600)}


def _expanding(ctx: StoryContext) -> QWidget:
    widget = QWidget()
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget


def _label(ctx: StoryContext) -> QWidget:
    return QLabel("label")


def _make_registry() -> StoryRegistry:
    registry = StoryRegistry()
    registry.story("Fill/Story", layout=Layout.FILL)(_expanding)
    registry.story("Padded/Story", layout=Layout.PADDED)(_label)
    return registry


def _make_window(
    qtbot, themes: BuiltinThemeProvider, registry: StoryRegistry | None = None, *, width: int = 1100, height: int = 700
) -> GalleryWindow:
    window = GalleryWindow(registry if registry is not None else _make_registry(), themes)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    return window


def _combo(window: QWidget, name: str) -> QComboBox:
    combo = window.findChild(QComboBox, name)
    assert combo is not None
    return combo


def _spin(window: QWidget, name: str) -> QSpinBox:
    spin = window.findChild(QSpinBox, name)
    assert spin is not None
    return spin


def _canvas(window: QWidget) -> Canvas:
    canvas = window.findChild(Canvas, "sbkCanvas")
    assert canvas is not None
    return canvas


def _surface(window: QWidget) -> QFrame:
    surface = window.findChild(QFrame, "sbkPreviewSurface")
    assert surface is not None
    return surface


def _scroll(window: QWidget) -> QScrollArea:
    scroll = window.findChild(QScrollArea, "sbkPreviewScroll")
    assert scroll is not None
    return scroll


def _choose(combo: QComboBox, text: str) -> None:
    index = combo.findText(text)
    assert index >= 0, text
    combo.setCurrentIndex(index)
    QApplication.processEvents()


def _choose_size(window: QWidget, name: str) -> None:
    combo = _combo(window, "sbkCanvasSize")
    index = next(i for i in range(combo.count()) if combo.itemText(i).startswith(name))
    combo.setCurrentIndex(index)
    QApplication.processEvents()


def _story_widget(window: GalleryWindow) -> QWidget:
    widget = window.current_preview_widget()
    assert widget is not None
    return widget


def _size_label(window: QWidget) -> QLabel:
    label = window.findChild(QLabel, "sbkCanvasSizeLabel")
    assert label is not None
    return label


def _pixel_name(image: QImage, origin: QPoint, x: int, y: int) -> str:
    return image.pixelColor(origin.x() + x, origin.y() + y).name()


def _size_texts(window: QWidget) -> list[str]:
    combo = _combo(window, "sbkCanvasSize")
    return [combo.itemText(index) for index in range(combo.count())]


@pytest.mark.parametrize(
    ("background", "role"),
    [
        ("Window", QPalette.ColorRole.Window),
        ("Base", QPalette.ColorRole.Base),
        ("Alternate Base", QPalette.ColorRole.AlternateBase),
    ],
)
def test_a_background_sets_the_surfaces_background_role(qtbot, themes: BuiltinThemeProvider, background: str, role: QPalette.ColorRole) -> None:
    window = _make_window(qtbot, themes)

    _choose(_combo(window, "sbkCanvasBackground"), background)

    assert _surface(window).backgroundRole() == role
    assert _canvas(window).background() is CanvasBackground(background)


def test_the_default_background_is_window_and_the_options_are_listed_in_order(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    combo = _combo(window, "sbkCanvasBackground")

    assert [combo.itemText(index) for index in range(combo.count())] == ["Window", "Base", "Alternate Base", "Checkerboard"]
    assert combo.currentText() == "Window"
    assert _surface(window).backgroundRole() == QPalette.ColorRole.Window


def test_the_checkerboard_is_painted_from_the_palette_and_leaves_the_story_palette_alone(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, width=900, height=600)
    preview = _story_widget(window)
    window_color = preview.palette().window().color()
    surface_window_brush = _surface(window).palette().window()

    _choose(_combo(window, "sbkCanvasBackground"), "Checkerboard")

    assert _surface(window).backgroundRole() == QPalette.ColorRole.Window
    assert preview.palette().window().color() == window_color
    assert _surface(window).palette().window() == surface_window_brush
    assert _surface(window).palette().window().style().name == "SolidPattern"


def test_the_checkerboard_alternates_eight_pixel_squares_of_base_and_mid_and_follows_a_theme_switch(qtbot, themes: BuiltinThemeProvider) -> None:
    registry = StoryRegistry()
    window = _make_window(qtbot, themes, registry, width=900, height=600)
    _choose(_combo(window, "sbkCanvasBackground"), "Checkerboard")

    for theme in ("Light", "Dark"):
        window.set_theme(theme)
        QApplication.processEvents()
        surface = _surface(window)
        palette = surface.palette()
        image = surface.grab().toImage()
        # Sample whole squares below the surface's children (the empty-state label), whose antialiased text can reach into the first squares.
        covered = max((child.geometry().bottom() + 1 for child in surface.findChildren(QWidget) if child.isVisible()), default=0)
        origin = surface.contentsRect().topLeft() + QPoint(0, -(-covered // 16) * 16)
        assert origin.y() + 16 <= surface.contentsRect().bottom()
        pixel = functools.partial(_pixel_name, image, origin)

        mid = palette.color(QPalette.ColorRole.Mid).name()
        base = palette.color(QPalette.ColorRole.Base).name()
        assert mid != base
        assert (pixel(1, 1), pixel(7, 7)) == (mid, mid)
        assert (pixel(9, 1), pixel(1, 9), pixel(15, 7)) == (base, base, base)
        assert (pixel(9, 9), pixel(15, 15)) == (mid, mid)


def test_base_keeps_meaning_the_themes_base_after_a_theme_switch(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, StoryRegistry(), width=900, height=600)
    _choose(_combo(window, "sbkCanvasBackground"), "Base")
    colors = []

    for theme in ("Light", "Dark"):
        window.set_theme(theme)
        QApplication.processEvents()
        surface = _surface(window)
        expected = surface.palette().color(QPalette.ColorRole.Base)
        origin = surface.contentsRect().topLeft()
        assert surface.backgroundRole() == QPalette.ColorRole.Base
        assert surface.grab().toImage().pixelColor(origin.x() + 2, origin.y() + 2) == expected
        colors.append(expected.name())

    assert colors[0] != colors[1]


@pytest.mark.parametrize("name", sorted(_BUILTIN_SIZES))
def test_a_built_in_size_gives_a_fill_story_exactly_that_size(qtbot, themes: BuiltinThemeProvider, name: str) -> None:
    window = _make_window(qtbot, themes)
    width, height = _BUILTIN_SIZES[name]

    _choose_size(window, name)

    assert _story_widget(window).size() == QSize(width, height)
    assert _canvas(window).active_size() == QSize(width, height)


def test_a_size_larger_than_the_window_still_gives_the_exact_size_and_scrolls(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes, width=700, height=500)

    _choose_size(window, "Dialog")

    assert _story_widget(window).size() == QSize(800, 600)
    scroll = _scroll(window)
    assert scroll.horizontalScrollBar().maximum() > 0
    assert scroll.verticalScrollBar().maximum() > 0


def test_a_custom_size_shows_its_spin_boxes_and_gives_a_fill_story_exactly_that_size(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    width, height = _spin(window, "sbkCanvasWidth"), _spin(window, "sbkCanvasHeight")
    assert not width.isVisible()
    assert not height.isVisible()

    _choose_size(window, "Custom")

    assert width.isVisible()
    assert height.isVisible()
    assert (width.minimum(), width.maximum(), height.minimum(), height.maximum()) == (1, 10_000, 1, 10_000)
    width.setValue(333)
    height.setValue(222)
    QApplication.processEvents()
    assert _story_widget(window).size() == QSize(333, 222)
    assert _size_label(window).text() == "333 \u00d7 222"


def test_choosing_custom_after_a_preset_starts_at_that_presets_size(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    _choose_size(window, "Phone portrait")

    _choose_size(window, "Custom")

    assert (_spin(window, "sbkCanvasWidth").value(), _spin(window, "sbkCanvasHeight").value()) == (320, 480)
    assert _story_widget(window).size() == QSize(320, 480)


def test_a_size_outlines_the_surface_and_fit_restores_the_unsized_canvas(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    scroll, surface = _scroll(window), _surface(window)
    fit_size = surface.size()
    assert surface.frameShape() == QFrame.Shape.NoFrame
    assert scroll.widgetResizable()

    _choose_size(window, "Dialog")

    assert surface.frameShape() == QFrame.Shape.StyledPanel
    assert not scroll.widgetResizable()
    layout = surface.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    frame = 2 * surface.frameWidth()
    assert surface.size() == QSize(800 + margins.left() + margins.right() + frame, 600 + margins.top() + margins.bottom() + frame)

    _choose_size(window, "Fit")

    assert surface.frameShape() == QFrame.Shape.NoFrame
    assert scroll.widgetResizable()
    assert surface.size() == fit_size
    assert _story_widget(window).geometry() == surface.rect().adjusted(10, 10, -10, -10)


def test_the_size_label_shows_only_while_a_size_is_active(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    label = _size_label(window)
    assert not label.isVisible()

    _choose_size(window, "Dialog")
    assert label.isVisible()
    assert label.text() == "800 × 600"

    _choose_size(window, "Fit")
    assert not label.isVisible()


def test_registry_presets_follow_the_built_in_sizes_and_precede_custom(qtbot, themes: BuiltinThemeProvider) -> None:
    registry = _make_registry()
    registry.size_presets.append(SizePreset("Tablet", 768, 1024))
    registry.size_presets.append(SizePreset("Watch", 200, 200))

    window = _make_window(qtbot, themes, registry)

    assert _size_texts(window) == [
        "Fit",
        "Phone portrait (320 × 480)",
        "Phone landscape (480 × 320)",
        "Dialog (800 × 600)",
        "Tablet (768 × 1024)",
        "Watch (200 × 200)",
        "Custom…",
    ]
    _choose_size(window, "Tablet")
    assert _story_widget(window).size() == QSize(768, 1024)


def test_a_preset_that_disappears_after_set_registry_falls_back_to_fit(qtbot, themes: BuiltinThemeProvider) -> None:
    registry = _make_registry()
    registry.size_presets.append(SizePreset("Tablet", 768, 1024))
    window = _make_window(qtbot, themes, registry)
    _choose_size(window, "Tablet")

    reloaded = _make_registry()
    window.set_registry(reloaded)
    QApplication.processEvents()

    assert _combo(window, "sbkCanvasSize").currentText() == "Fit"
    assert _canvas(window).active_size() is None
    assert _scroll(window).widgetResizable()
    assert "Tablet (768 × 1024)" not in _size_texts(window)


def test_a_preset_that_is_still_listed_and_a_custom_size_survive_set_registry(qtbot, themes: BuiltinThemeProvider) -> None:
    registry = _make_registry()
    registry.size_presets.append(SizePreset("Tablet", 768, 1024))
    window = _make_window(qtbot, themes, registry)
    _choose_size(window, "Tablet")

    reloaded = _make_registry()
    reloaded.size_presets.extend([SizePreset("Watch", 200, 200), SizePreset("Tablet", 768, 1024)])
    window.set_registry(reloaded)
    QApplication.processEvents()

    assert _combo(window, "sbkCanvasSize").currentText() == "Tablet (768 × 1024)"
    assert _story_widget(window).size() == QSize(768, 1024)

    _choose_size(window, "Custom")
    _spin(window, "sbkCanvasWidth").setValue(300)
    window.set_registry(_make_registry())
    QApplication.processEvents()

    assert _combo(window, "sbkCanvasSize").currentText() == "Custom…"
    assert _canvas(window).active_size() == QSize(300, 1024)


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (("", 1, 1), ValueError),
        (("  ", 1, 1), ValueError),
        (("A", 0, 1), ValueError),
        (("A", 1, -5), ValueError),
        (("Large", 2**31, 480), ValueError),
        (("X", 10_001, 10), ValueError),
        (("X", 10, 10_001), ValueError),
        (("A", True, 1), TypeError),
        (("A", 1, 2.5), TypeError),
        ((5, 1, 1), TypeError),
    ],
)
def test_a_size_preset_validates_its_fields(args: tuple, error: type[Exception]) -> None:
    with pytest.raises(error):
        SizePreset(*args)


def test_a_size_preset_accepts_the_largest_size_of_the_canvas() -> None:
    assert SizePreset("Huge", 10_000, 10_000).width == 10_000


def test_a_size_preset_is_frozen_and_compares_by_value() -> None:
    preset = SizePreset("Tablet", 768, 1024)

    assert preset == SizePreset("Tablet", 768, 1024)
    with pytest.raises(AttributeError):
        preset.width = 5  # ty: ignore[invalid-assignment]


def test_a_registry_has_no_size_presets_by_default() -> None:
    assert StoryRegistry().size_presets == []


def test_the_background_and_size_survive_switching_story_and_theme(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    _choose(_combo(window, "sbkCanvasBackground"), "Alternate Base")
    _choose_size(window, "Phone landscape")

    window.select_story("Padded/Story")
    window.set_theme("Dark")
    window.select_story("Fill/Story")
    QApplication.processEvents()

    assert _combo(window, "sbkCanvasBackground").currentText() == "Alternate Base"
    assert _surface(window).backgroundRole() == QPalette.ColorRole.AlternateBase
    assert _combo(window, "sbkCanvasSize").currentText().startswith("Phone landscape")
    assert _story_widget(window).size() == QSize(480, 320)


def test_a_padded_story_keeps_its_top_alignment_inside_a_size(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    window.select_story("Padded/Story")
    _choose_size(window, "Dialog")

    assert _story_widget(window).y() == _surface(window).contentsRect().top() + 10


def test_choosing_custom_does_not_widen_the_window_under_a_wide_font(qtbot, themes: BuiltinThemeProvider, restore_application_look: None) -> None:
    # The Width and Height boxes have a row of their own: next to Background and Size they made the toolbar wider than the default
    # window with the Windows fonts, and the window grew from 1100 to 1244 pixels.
    font = QApplication.font()
    font.setPointSizeF(font.pointSizeF() * 1.4)
    QApplication.setFont(font)
    window = _make_window(qtbot, themes)
    toolbar = window.findChild(QWidget, "sbkCanvasToolbar")
    assert toolbar is not None
    fit_minimum = toolbar.minimumSizeHint().width()
    fit_size = window.size()

    _choose_size(window, "Custom")

    assert _spin(window, "sbkCanvasWidth").isVisible()
    assert toolbar.minimumSizeHint().width() == fit_minimum
    assert window.size() == fit_size


@pytest.mark.parametrize("size", ["Fit", "Dialog", "Custom"])
def test_every_canvas_control_is_visible_and_at_least_its_minimum_size_hint_at_the_default_size(
    qtbot, themes: BuiltinThemeProvider, size: str
) -> None:
    window = _make_window(qtbot, themes)
    _choose_size(window, size)
    toolbar = window.findChild(QWidget, "sbkCanvasToolbar")
    assert toolbar is not None
    controls: list[QWidget] = [_combo(window, "sbkCanvasBackground"), _combo(window, "sbkCanvasSize")]
    if size == "Custom":
        controls += [_spin(window, "sbkCanvasWidth"), _spin(window, "sbkCanvasHeight")]
    if size != "Fit":
        controls.append(_size_label(window))
    controls += [label for label in toolbar.findChildren(QLabel) if label.buddy() is not None and not label.isHidden()]

    def fits() -> None:
        # The initial splitter sizes leave the middle pane wide enough for the longest toolbar row; wait for the posted layout pass.
        undersized = [
            f"{widget.objectName() or type(widget).__name__}: {widget.size().toTuple()} < {widget.minimumSizeHint().toTuple()}"
            for widget in [*controls, toolbar]
            if not widget.isVisible()
            or widget.width() < widget.minimumSizeHint().width()
            or widget.height() < widget.minimumSizeHint().height()
        ]
        assert not undersized, f"window {window.size().toTuple()}: " + ", ".join(undersized)

    qtbot.waitUntil(fits, timeout=3000)
    assert window.size() == QSize(1100, 700)
    assert len(controls) == {"Fit": 4, "Dialog": 5, "Custom": 9}[size]


def test_every_combo_and_spin_box_has_an_accessible_name_and_a_label_buddy(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    toolbar = window.findChild(QWidget, "sbkCanvasToolbar")
    assert toolbar is not None
    buddies = {label.buddy(): label.text() for label in toolbar.findChildren(QLabel) if label.buddy() is not None}

    for name, accessible, text in (
        ("sbkCanvasBackground", "Background", "Background"),
        ("sbkCanvasSize", "Size", "Size"),
        ("sbkCanvasWidth", "Width", "Width"),
        ("sbkCanvasHeight", "Height", "Height"),
    ):
        widget = toolbar.findChild(QWidget, name)
        assert widget is not None
        assert widget.accessibleName() == accessible
        assert buddies[widget] == text
    for combo in toolbar.findChildren(QComboBox):
        assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon


def test_the_toolbar_is_a_plain_widget_with_the_custom_size_boxes_on_a_row_of_their_own(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    toolbar = window.findChild(QWidget, "sbkCanvasToolbar")

    assert toolbar is not None
    assert type(toolbar) is QWidget
    layout = toolbar.layout()
    assert layout is not None
    assert layout.count() == 3
    custom_item = layout.itemAt(1)
    assert custom_item is not None
    custom_row = custom_item.layout()
    assert custom_row is not None
    row_items = [custom_row.itemAt(index) for index in range(custom_row.count())]
    row_widgets = [item.widget() for item in row_items if item is not None]
    width, height = _spin(window, "sbkCanvasWidth"), _spin(window, "sbkCanvasHeight")
    assert [widget for widget in row_widgets if isinstance(widget, QSpinBox)] == [width, height]
    assert [widget.buddy() for widget in row_widgets if isinstance(widget, QLabel)] == [width, height]


def test_place_and_clear_work_on_a_canvas_on_its_own(qtbot) -> None:
    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(500, 400)
    canvas.show()
    widget = QLabel("hello", canvas.surface)

    canvas.place(widget, Layout.CENTERED)
    QApplication.processEvents()
    assert widget.parent() is canvas.surface
    assert not widget.isHidden()

    canvas.clear()
    assert widget.isHidden()


def test_the_size_list_shows_every_name_in_full_although_the_box_elides_it(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _make_window(qtbot, themes)
    combo = _combo(window, "sbkCanvasSize")
    view = combo.view()

    combo.showPopup()
    try:
        qtbot.waitUntil(lambda: view.isVisible(), timeout=3000)
        assert view.width() >= view.sizeHintForColumn(0)
        assert view.width() > combo.width()
    finally:
        combo.hidePopup()
