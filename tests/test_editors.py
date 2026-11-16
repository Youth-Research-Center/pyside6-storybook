from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import TypeVar

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPalette, QTextCursor, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook import BoolControl, ChoiceControl, ColorControl, EnumControl, FileControl, FloatControl, IntControl, TextControl
from pyside6_storybook.controls import Control
from pyside6_storybook.gui.editors import EDITORS, ControlEditor, color_editor, create_editor, file_editor

pytestmark = pytest.mark.usefixtures("restore_window_activation")

_WidgetT = TypeVar("_WidgetT", bound=QWidget)
_HOSTS: list[QWidget] = []
"""The windows of the editors under test, kept alive until the test ends (``qtbot`` holds its widgets weakly)."""


@pytest.fixture(autouse=True)
def _release_hosts() -> Iterator[None]:
    try:
        yield
    finally:
        _HOSTS.clear()


class _Mode(Enum):
    FIRST = 1
    SECOND = 2
    THIRD = 3


class _Recorder:
    """Collects what an editor emits."""

    def __init__(self, editor: ControlEditor) -> None:
        self.values: list[object] = []
        editor.valueChanged.connect(self.values.append)


def _make(qtbot, control: Control, value: object | None = None) -> tuple[ControlEditor, _Recorder]:
    """Show an editor in a window next to a line edit that can take focus away from it."""
    host = QWidget()
    qtbot.addWidget(host)
    _HOSTS.append(host)
    layout = QVBoxLayout(host)
    other = QLineEdit(host)
    other.setObjectName("other")
    editor = create_editor(control, control.coerce(control.default) if value is None else value, host)
    layout.addWidget(other)
    layout.addWidget(editor)
    host.show()
    qtbot.waitExposed(host)
    return editor, _Recorder(editor)


def _child(editor: QWidget, widget_type: type[_WidgetT]) -> _WidgetT:
    child = editor.findChild(widget_type)
    assert child is not None, widget_type.__name__
    return child


def _wheel(widget: QWidget, delta: int = 120) -> QWheelEvent:
    """Send a wheel event to ``widget`` and return it, so the test can ask whether it was accepted."""
    event = QWheelEvent(
        QPointF(widget.rect().center()),
        QPointF(widget.mapToGlobal(widget.rect().center())),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,  # noqa: FBT003 (QWheelEvent's signature)
    )
    QApplication.sendEvent(widget, event)
    return event


def _focus(qtbot, widget: QWidget) -> None:
    widget.window().activateWindow()
    widget.setFocus()
    qtbot.waitUntil(widget.hasFocus)


def test_every_control_type_has_an_editor_and_an_unknown_one_is_rejected() -> None:
    assert set(EDITORS) == {TextControl, BoolControl, ChoiceControl, IntControl, FloatControl, ColorControl, EnumControl, FileControl}
    with pytest.raises(TypeError, match="Unsupported control type"):
        create_editor(object(), 1)  # ty: ignore[invalid-argument-type]


def test_a_subclass_of_a_control_gets_its_base_class_editor(qtbot) -> None:
    class PercentControl(IntControl):
        pass

    editor = create_editor(PercentControl("p", 5, 0, 100), 5)
    qtbot.addWidget(editor)
    assert type(editor) is EDITORS[IntControl]
    assert editor.value() == 5


def test_the_base_editor_has_no_value(qtbot) -> None:
    editor = ControlEditor()
    qtbot.addWidget(editor)
    with pytest.raises(NotImplementedError):
        editor.value()


def test_text_editor_emits_once_per_keystroke_and_not_for_the_same_text(qtbot) -> None:
    editor, recorder = _make(qtbot, TextControl("text", ""))
    line_edit = _child(editor, QLineEdit)

    qtbot.keyClicks(line_edit, "ab")
    assert recorder.values == ["a", "ab"]
    assert editor.value() == "ab"

    line_edit.setText("ab")
    assert recorder.values == ["a", "ab"]


def test_text_editor_starts_with_the_given_value_without_emitting(qtbot) -> None:
    editor, recorder = _make(qtbot, TextControl("text", "default"), "given")
    assert editor.value() == "given"
    assert recorder.values == []


def test_multiline_text_editor_is_a_plain_text_edit_that_emits_once_per_keystroke(qtbot) -> None:
    editor, recorder = _make(qtbot, TextControl("text", "a", multiline=True))
    plain = _child(editor, QPlainTextEdit)
    assert editor.findChild(QLineEdit) is None
    assert editor.focusProxy() is plain
    plain.moveCursor(QTextCursor.MoveOperation.End)

    qtbot.keyClick(plain, Qt.Key.Key_Return)
    qtbot.keyClicks(plain, "bc")

    assert recorder.values == ["a\n", "a\nb", "a\nbc"]
    assert editor.value() == "a\nbc"


def test_multiline_text_editor_lets_tab_leave_it(qtbot) -> None:
    editor, _recorder = _make(qtbot, TextControl("text", "", multiline=True))
    assert _child(editor, QPlainTextEdit).tabChangesFocus()


def test_bool_editor_emits_once_per_click(qtbot) -> None:
    editor, recorder = _make(qtbot, BoolControl("flag", default=False))
    check_box = _child(editor, QCheckBox)

    qtbot.mouseClick(check_box, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(check_box, Qt.MouseButton.LeftButton)

    assert recorder.values == [True, False]
    assert editor.value() is False


def test_bool_editor_toggles_with_the_space_key(qtbot) -> None:
    editor, recorder = _make(qtbot, BoolControl("flag", default=False))
    _focus(qtbot, _child(editor, QCheckBox))

    qtbot.keyClick(_child(editor, QCheckBox), Qt.Key.Key_Space)

    assert recorder.values == [True]


def test_choice_editor_emits_the_option_once_per_change(qtbot) -> None:
    editor, recorder = _make(qtbot, ChoiceControl("role", "b", ("a", "b", "c")))
    combo = _child(editor, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["a", "b", "c"]
    assert editor.value() == "b"

    combo.setCurrentIndex(2)
    combo.setCurrentIndex(2)

    assert recorder.values == ["c"]
    assert editor.value() == "c"


def test_int_editor_uses_range_and_step(qtbot) -> None:
    editor, _recorder = _make(qtbot, IntControl("n", 10, 0, 100, step=5))
    spin_box = _child(editor, QSpinBox)
    assert (spin_box.minimum(), spin_box.maximum(), spin_box.value(), spin_box.singleStep()) == (0, 100, 10, 5)
    assert editor.findChild(QSlider) is None


def test_int_editor_emits_once_per_typed_value_and_arrow_press(qtbot) -> None:
    editor, recorder = _make(qtbot, IntControl("n", 5, 0, 100, step=5))
    spin_box = _child(editor, QSpinBox)

    spin_box.selectAll()
    qtbot.keyClicks(spin_box, "40")
    assert recorder.values[-1] == 40

    recorder.values.clear()
    qtbot.keyClick(spin_box, Qt.Key.Key_Up)
    assert recorder.values == [45]
    assert editor.value() == 45


def test_int_editor_slider_and_spin_box_mirror_each_other_with_one_emit_per_edit(qtbot) -> None:
    editor, recorder = _make(qtbot, IntControl("n", 10, 0, 100, slider=True))
    spin_box = _child(editor, QSpinBox)
    slider = _child(editor, QSlider)
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 100, 10)

    slider.setValue(60)
    assert (spin_box.value(), slider.value(), recorder.values) == (60, 60, [60])

    spin_box.setValue(25)
    assert (spin_box.value(), slider.value(), recorder.values) == (25, 25, [60, 25])

    spin_box.setValue(25)
    assert recorder.values == [60, 25]
    assert editor.value() == 25


def test_int_editor_slider_uses_the_step(qtbot) -> None:
    editor, recorder = _make(qtbot, IntControl("n", 0, 0, 100, step=10, slider=True))
    slider = _child(editor, QSlider)
    assert slider.singleStep() == 10
    _focus(qtbot, slider)

    qtbot.keyClick(slider, Qt.Key.Key_Right)

    assert recorder.values == [10]


def test_float_editor_uses_range_step_and_decimals(qtbot) -> None:
    editor, _recorder = _make(qtbot, FloatControl("x", 0.5, 0.0, 1.0, step=0.25, decimals=3))
    spin_box = _child(editor, QDoubleSpinBox)
    assert (spin_box.minimum(), spin_box.maximum(), spin_box.value()) == (0.0, 1.0, 0.5)
    assert (spin_box.singleStep(), spin_box.decimals()) == (0.25, 3)
    assert editor.findChild(QSlider) is None


def test_float_editor_emits_once_per_typed_value(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.5, 0.0, 1.0))
    spin_box = _child(editor, QDoubleSpinBox)

    spin_box.selectAll()
    qtbot.keyClicks(spin_box, "0.25")

    assert recorder.values[-1] == pytest.approx(0.25)
    assert editor.value() == pytest.approx(0.25)


def test_float_editor_slider_reaches_the_maximum_exactly(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.0, 0.0, 0.07, step=0.01, slider=True))
    slider = _child(editor, QSlider)
    assert (slider.minimum(), slider.maximum()) == (0, 7)

    slider.setValue(7)

    assert recorder.values == [0.07]
    assert editor.value() == 0.07


def test_float_editor_slider_last_position_is_the_maximum_when_the_step_does_not_divide_the_range(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.0, 0.0, 2.1, step=0.7, slider=True))
    slider = _child(editor, QSlider)
    assert slider.maximum() == 3

    slider.setValue(1)
    slider.setValue(3)

    assert recorder.values == [0.7, 2.1]


def test_float_editor_slider_last_position_is_the_maximum_when_the_tolerance_drops_a_tiny_last_interval(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.0, 0.0, 1.0000000001, step=1.0, decimals=10, slider=True))
    slider = _child(editor, QSlider)
    assert slider.maximum() == 1

    slider.setValue(1)

    assert recorder.values == [1.0000000001]


@pytest.mark.parametrize(("value", "position"), [(1.0, 4), (0.96, 4), (0.9, 3), (0.94, 3), (0.2, 1)])
def test_float_editor_slider_follows_the_spin_box_to_the_nearest_position_including_a_short_last_interval(
    qtbot, value: float, position: int
) -> None:
    editor, _recorder = _make(qtbot, FloatControl("x", 0.0, 0.0, 1.0, step=0.3, slider=True))
    slider = _child(editor, QSlider)
    assert slider.maximum() == 4

    _child(editor, QDoubleSpinBox).setValue(value)

    assert slider.value() == position


def test_float_editor_slider_position_is_a_step_from_the_minimum(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 1.0, 1.0, 2.0, step=0.25, slider=True))
    slider = _child(editor, QSlider)

    slider.setValue(2)

    assert recorder.values == [1.5]
    assert _child(editor, QDoubleSpinBox).value() == 1.5


def test_float_editor_slider_and_spin_box_mirror_each_other_with_one_emit_per_edit(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.0, 0.0, 1.0, step=0.25, slider=True))
    spin_box = _child(editor, QDoubleSpinBox)
    slider = _child(editor, QSlider)

    spin_box.setValue(0.3)
    assert (slider.value(), spin_box.value(), recorder.values) == (1, 0.3, [0.3])

    spin_box.setValue(0.3)
    assert recorder.values == [0.3]

    slider.setValue(4)
    assert (spin_box.value(), recorder.values) == (1.0, [0.3, 1.0])


def test_float_editor_slider_starts_at_the_position_nearest_the_value(qtbot) -> None:
    editor, recorder = _make(qtbot, FloatControl("x", 0.4, 0.0, 1.0, step=0.25, slider=True))
    assert _child(editor, QSlider).value() == 2
    assert recorder.values == []
    assert editor.value() == 0.4


def test_float_editor_on_a_zero_width_range_has_a_one_position_slider(qtbot) -> None:
    editor, _recorder = _make(qtbot, FloatControl("x", 5.0, 5.0, 5.0, slider=True))
    slider = _child(editor, QSlider)
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 0, 0)
    assert editor.value() == 5.0


@pytest.mark.parametrize(
    ("control", "widget_type"),
    [
        (IntControl("n", 5, 0, 10, slider=True), QSpinBox),
        (IntControl("n", 5, 0, 10, slider=True), QSlider),
        (FloatControl("x", 0.5, 0.0, 1.0, slider=True), QDoubleSpinBox),
        (FloatControl("x", 0.5, 0.0, 1.0, slider=True), QSlider),
        (ChoiceControl("c", "b", ("a", "b", "c")), QComboBox),
        (EnumControl("e", _Mode.SECOND), QComboBox),
    ],
)
def test_wheel_is_ignored_without_focus_and_acts_with_it(qtbot, control: Control, widget_type: type[QWidget]) -> None:
    editor, recorder = _make(qtbot, control)
    widget = _child(editor, widget_type)
    assert widget.focusPolicy() == Qt.FocusPolicy.StrongFocus
    before = editor.value()
    other = editor.window().findChild(QLineEdit, "other")
    assert other is not None
    _focus(qtbot, other)
    assert not widget.hasFocus()

    event = _wheel(widget)

    assert not event.isAccepted()
    assert editor.value() == before
    assert recorder.values == []

    _focus(qtbot, widget)
    event = _wheel(widget)

    assert event.isAccepted()
    assert editor.value() != before
    assert len(recorder.values) == 1


def test_wheel_filter_is_owned_by_its_widget(qtbot) -> None:
    editor, _recorder = _make(qtbot, IntControl("n", 5, 0, 10))
    spin_box = _child(editor, QSpinBox)
    assert [child for child in spin_box.children() if type(child).__name__ == "_WheelFilter"]


@pytest.mark.parametrize(
    "control",
    [
        TextControl("t", "x"),
        TextControl("t", "x", multiline=True),
        BoolControl("b", default=True),
        ChoiceControl("c", "x", ("x",)),
        IntControl("i", 1, 0, 2),
        IntControl("i", 1, 0, 2, slider=True),
        FloatControl("f", 1.0, 0.0, 2.0),
        FloatControl("f", 1.0, 0.0, 2.0, slider=True),
        ColorControl("c", "#336699"),
        EnumControl("e", _Mode.FIRST),
        FileControl("p", "a.txt"),
    ],
)
def test_the_primary_input_is_the_focus_proxy_and_gets_the_accessible_texts(qtbot, control: Control) -> None:
    editor, _recorder = _make(qtbot, control)

    editor.set_accessible_texts("Opacity", "How see-through")

    proxy = editor.focusProxy()
    assert proxy is not None
    assert editor.isAncestorOf(proxy)
    assert proxy.accessibleName() == "Opacity"
    assert proxy.accessibleDescription() == "How see-through"
    assert proxy.focusPolicy() != Qt.FocusPolicy.NoFocus
    slider = editor.findChild(QSlider)
    if getattr(control, "slider", False):
        assert slider is not None
        assert slider.accessibleName() == "Opacity slider"
        assert slider.accessibleDescription() == "How see-through"
        assert slider is not proxy
    else:
        assert slider is None


def test_the_spin_box_is_the_focus_proxy_of_a_composite_editor(qtbot) -> None:
    int_editor, _ = _make(qtbot, IntControl("n", 1, 0, 2, slider=True))
    float_editor, _ = _make(qtbot, FloatControl("x", 1.0, 0.0, 2.0, slider=True))
    assert int_editor.focusProxy() is _child(int_editor, QSpinBox)
    assert float_editor.focusProxy() is _child(float_editor, QDoubleSpinBox)


def test_every_part_of_an_editor_is_a_descendant_of_it(qtbot) -> None:
    editor, _recorder = _make(qtbot, FloatControl("x", 1.0, 0.0, 2.0, slider=True))
    for widget_type in (QDoubleSpinBox, QSlider):
        assert _child(editor, widget_type).parent() is editor


def test_color_editor_starts_with_the_value_without_emitting(qtbot) -> None:
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    assert editor.value() == QColor("#336699")
    assert _child(editor, QLineEdit).text() == "#336699"
    assert _child(editor, QPushButton).text() == "#336699"
    assert not _child(editor, QPushButton).icon().isNull()
    assert recorder.values == []


def test_color_editor_redraws_the_swatch_border_when_the_palette_changes(qtbot) -> None:
    editor, _recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    swatch = _child(editor, QPushButton)

    def border() -> QColor:
        return swatch.icon().pixmap(swatch.iconSize()).toImage().pixelColor(0, 0)

    palette = editor.palette()
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#ff0000"))
    editor.setPalette(palette)
    assert border() == QColor("#ff0000")
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#00ff00"))
    editor.setPalette(palette)
    assert border() == QColor("#00ff00")


def test_color_editor_value_is_a_new_object(qtbot) -> None:
    editor, _recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    value = editor.value()
    assert isinstance(value, QColor)
    value.setRed(0)
    assert editor.value() == QColor("#336699")


def test_color_editor_emits_the_color_chosen_in_the_dialog(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[QColor, bool]] = []

    def fake(parent: QWidget, initial: QColor, *, alpha: bool, title: str) -> QColor | None:
        asked.append((initial, alpha))
        return QColor("#ff0000")

    monkeypatch.setattr(color_editor, "_ask_color", fake)
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))

    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)

    assert asked == [(QColor("#336699"), False)]
    assert recorder.values == [QColor("#ff0000")]
    assert editor.value() == QColor("#ff0000")
    assert _child(editor, QLineEdit).text() == "#ff0000"
    assert _child(editor, QPushButton).text() == "#ff0000"


def test_color_editor_does_not_emit_when_the_dialog_returns_the_same_color_and_ignores_a_cancel(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[QColor | None] = [QColor("#336699"), None]
    monkeypatch.setattr(color_editor, "_ask_color", lambda *_args, **_kwargs: answers.pop(0))
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))

    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)
    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)

    assert recorder.values == []
    assert editor.value() == QColor("#336699")


def test_color_editor_asks_for_alpha_only_when_the_control_allows_it(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    alphas: list[bool] = []

    def fake(parent: QWidget, initial: QColor, *, alpha: bool, title: str) -> QColor | None:
        alphas.append(alpha)
        return None

    monkeypatch.setattr(color_editor, "_ask_color", fake)
    editor, _recorder = _make(qtbot, ColorControl("c", "#33669980", alpha=True), QColor(0x33, 0x66, 0x99, 0x80))
    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)
    assert alphas == [True]
    assert _child(editor, QLineEdit).text() == "#33669980"


def test_color_editor_keeps_a_finer_than_8_bit_colour_when_return_is_pressed_on_unchanged_text(qtbot) -> None:
    fine = QColor.fromRgbF(0.1, 0.2, 0.3)
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), fine)
    line_edit = _child(editor, QLineEdit)
    _focus(qtbot, line_edit)

    qtbot.keyClick(line_edit, Qt.Key.Key_Return)

    assert recorder.values == []
    assert editor.value() == fine
    assert line_edit.text() == "#1a334d"


def test_color_editor_commits_a_typed_hex_value_once_even_after_focus_leaves(qtbot) -> None:
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    line_edit = _child(editor, QLineEdit)
    _focus(qtbot, line_edit)
    line_edit.selectAll()

    qtbot.keyClicks(line_edit, "#FF8800")
    assert recorder.values == []
    qtbot.keyClick(line_edit, Qt.Key.Key_Return)
    other = editor.window().findChild(QLineEdit, "other")
    assert other is not None
    _focus(qtbot, other)

    assert recorder.values == [QColor("#ff8800")]
    assert line_edit.text() == "#ff8800"


def test_color_editor_reverts_an_invalid_hex_value(qtbot) -> None:
    editor, recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    line_edit = _child(editor, QLineEdit)
    _focus(qtbot, line_edit)

    for bad in ("red", "#abc", "#12345678"):
        line_edit.selectAll()
        qtbot.keyClicks(line_edit, bad)
        qtbot.keyClick(line_edit, Qt.Key.Key_Return)
        assert line_edit.text() == "#336699"

    assert recorder.values == []
    assert editor.value() == QColor("#336699")


def test_color_editor_buttons_are_named_and_the_hex_field_is_the_focus_proxy(qtbot) -> None:
    editor, _recorder = _make(qtbot, ColorControl("c", "#336699"), QColor("#336699"))
    editor.set_accessible_texts("Accent", "The accent colour")
    swatch = _child(editor, QPushButton)
    assert swatch.accessibleName() == "Choose colour for Accent"
    assert swatch.accessibleDescription() == "The accent colour"
    assert swatch.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert editor.focusProxy() is _child(editor, QLineEdit)


def test_enum_editor_lists_the_option_names_and_emits_the_member_once_per_change(qtbot) -> None:
    editor, recorder = _make(qtbot, EnumControl("mode", _Mode.SECOND), _Mode.SECOND)
    combo = _child(editor, QComboBox)
    assert [combo.itemText(row) for row in range(combo.count())] == ["FIRST", "SECOND", "THIRD"]
    assert editor.value() is _Mode.SECOND

    combo.setCurrentIndex(2)

    assert recorder.values == [_Mode.THIRD]
    assert editor.value() is _Mode.THIRD


def test_enum_editor_offers_the_named_combinations_of_a_qt_flag(qtbot) -> None:
    editor, recorder = _make(qtbot, EnumControl("alignment", Qt.AlignmentFlag.AlignCenter), Qt.AlignmentFlag.AlignCenter)
    combo = _child(editor, QComboBox)
    names = [combo.itemText(row) for row in range(combo.count())]
    assert "AlignCenter" in names
    assert editor.value() == Qt.AlignmentFlag.AlignCenter

    combo.setCurrentIndex(names.index("AlignLeft"))

    assert recorder.values == [Qt.AlignmentFlag.AlignLeft]


def test_file_editor_starts_with_the_path_without_emitting(qtbot) -> None:
    editor, recorder = _make(qtbot, FileControl("p", "a/b.txt"), Path("a/b.txt"))
    assert _child(editor, QLineEdit).text() == str(Path("a/b.txt"))
    assert editor.value() == Path("a/b.txt")
    assert _child(editor, QPushButton).text() == "Browse…"
    assert recorder.values == []


def test_file_editor_emits_the_path_chosen_in_the_dialog(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[Path | None, str]] = []

    def fake(parent: QWidget, current: Path | None, *, name_filter: str, title: str) -> Path | None:
        asked.append((current, name_filter))
        return Path("chosen.png")

    monkeypatch.setattr(file_editor, "_ask_file", fake)
    editor, recorder = _make(qtbot, FileControl("p", filter="Images (*.png)"), None)

    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)

    assert asked == [(None, "Images (*.png)")]
    assert recorder.values == [Path("chosen.png")]
    assert editor.value() == Path("chosen.png")
    assert _child(editor, QLineEdit).text() == "chosen.png"


def test_file_editor_ignores_a_cancelled_dialog(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_editor, "_ask_file", lambda *_args, **_kwargs: None)
    editor, recorder = _make(qtbot, FileControl("p", "a.txt"), Path("a.txt"))

    qtbot.mouseClick(_child(editor, QPushButton), Qt.MouseButton.LeftButton)

    assert recorder.values == []
    assert editor.value() == Path("a.txt")
    assert _child(editor, QLineEdit).text() == "a.txt"


def test_file_editor_commits_a_typed_path_once_even_after_focus_leaves(qtbot) -> None:
    editor, recorder = _make(qtbot, FileControl("p"), None)
    line_edit = _child(editor, QLineEdit)
    _focus(qtbot, line_edit)

    qtbot.keyClicks(line_edit, "docs/readme.md")
    assert recorder.values == []
    qtbot.keyClick(line_edit, Qt.Key.Key_Return)
    other = editor.window().findChild(QLineEdit, "other")
    assert other is not None
    _focus(qtbot, other)

    assert recorder.values == [Path("docs/readme.md")]
    assert editor.value() == Path("docs/readme.md")


def test_file_editor_emits_none_when_the_field_is_emptied(qtbot) -> None:
    editor, recorder = _make(qtbot, FileControl("p", "a.txt"), Path("a.txt"))
    line_edit = _child(editor, QLineEdit)
    _focus(qtbot, line_edit)
    line_edit.selectAll()

    qtbot.keyClick(line_edit, Qt.Key.Key_Delete)
    qtbot.keyClick(line_edit, Qt.Key.Key_Return)

    assert recorder.values == [None]
    assert editor.value() is None


def test_file_editor_browse_button_is_named_and_the_path_field_is_the_focus_proxy(qtbot) -> None:
    editor, _recorder = _make(qtbot, FileControl("p"), None)
    editor.set_accessible_texts("Image", "The picture")
    browse = _child(editor, QPushButton)
    assert browse.accessibleName() == "Browse for Image"
    assert browse.accessibleDescription() == "The picture"
    assert browse.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert editor.focusProxy() is _child(editor, QLineEdit)
