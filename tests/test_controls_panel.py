from typing import TypeVar

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QLineEdit, QSpinBox, QWidget

from pyside6_storybook import BoolControl, ChoiceControl, FloatControl, IntControl, TextControl
from pyside6_storybook.gui.controls_panel import NO_CONTROLS_MESSAGE, ControlsPanel

_EditorT = TypeVar("_EditorT", bound=QWidget)


def _editor(panel: ControlsPanel, editor_type: type[_EditorT]) -> _EditorT:
    editor = panel.findChild(editor_type)
    assert editor is not None, editor_type.__name__
    return editor


def _emitted(panel: ControlsPanel) -> list[dict]:
    emitted: list[dict] = []
    panel.valuesChanged.connect(emitted.append)
    return emitted


def test_values_reflect_defaults(qtbot) -> None:
    panel = ControlsPanel([TextControl("text", "hi"), BoolControl("enabled", default=True)])
    qtbot.addWidget(panel)
    assert panel.values() == {"text": "hi", "enabled": True}


def test_values_returns_a_copy(qtbot) -> None:
    panel = ControlsPanel([TextControl("text", "hi")])
    qtbot.addWidget(panel)
    panel.values()["text"] = "changed"
    assert panel.values() == {"text": "hi"}


def test_text_editor_emits_once_per_keystroke(qtbot) -> None:
    panel = ControlsPanel([TextControl("text", "")])
    qtbot.addWidget(panel)
    emitted = _emitted(panel)
    editor = panel.findChild(QLineEdit)
    assert editor is not None

    qtbot.keyClicks(editor, "ab")

    assert emitted == [{"text": "a"}, {"text": "ab"}]
    assert panel.values() == {"text": "ab"}


def test_bool_editor_emits_when_clicked(qtbot) -> None:
    panel = ControlsPanel([BoolControl("enabled", default=False)])
    qtbot.addWidget(panel)
    panel.show()
    emitted = _emitted(panel)
    editor = panel.findChild(QCheckBox)
    assert editor is not None

    qtbot.mouseClick(editor, Qt.MouseButton.LeftButton)

    assert emitted == [{"enabled": True}]
    assert panel.values() == {"enabled": True}


def test_choice_editor_lists_options_and_emits_the_chosen_one(qtbot) -> None:
    panel = ControlsPanel([ChoiceControl("role", "secondary", ["primary", "secondary", "danger"])])
    qtbot.addWidget(panel)
    emitted = _emitted(panel)
    combo = panel.findChild(QComboBox)
    assert combo is not None
    assert [combo.itemText(i) for i in range(combo.count())] == ["primary", "secondary", "danger"]
    assert combo.currentText() == "secondary"

    combo.setCurrentIndex(2)

    assert emitted == [{"role": "danger"}]
    assert panel.values() == {"role": "danger"}


def test_int_editor_uses_the_range_and_emits_typed_values(qtbot) -> None:
    panel = ControlsPanel([IntControl("count", 5, 1, 20)])
    qtbot.addWidget(panel)
    panel.show()
    emitted = _emitted(panel)
    spin_box = panel.findChild(QSpinBox)
    assert spin_box is not None
    assert (spin_box.minimum(), spin_box.maximum(), spin_box.value()) == (1, 20, 5)

    spin_box.selectAll()
    qtbot.keyClicks(spin_box, "12")

    assert emitted[-1] == {"count": 12}
    assert panel.values() == {"count": 12}

    qtbot.keyClick(spin_box, Qt.Key.Key_Up)
    assert panel.values() == {"count": 13}


def test_float_editor_uses_the_range_and_emits(qtbot) -> None:
    panel = ControlsPanel([FloatControl("opacity", 0.5, 0.0, 1.0)])
    qtbot.addWidget(panel)
    panel.show()
    emitted = _emitted(panel)
    spin_box = panel.findChild(QDoubleSpinBox)
    assert spin_box is not None
    assert (spin_box.minimum(), spin_box.maximum(), spin_box.value()) == (0.0, 1.0, 0.5)
    assert spin_box.singleStep() == pytest.approx(0.01)
    assert spin_box.decimals() == 2

    spin_box.selectAll()
    qtbot.keyClicks(spin_box, "0.25")

    assert emitted[-1] == {"opacity": pytest.approx(0.25)}
    assert panel.values() == {"opacity": pytest.approx(0.25)}


@pytest.mark.parametrize(
    ("minimum", "maximum", "step", "decimals"),
    [(0.0, 1.0, 0.01, 2), (0.0, 100.0, 1.0, 2), (0.0, 0.01, 0.0001, 4), (5.0, 5.0, 1.0, 2)],
)
def test_float_step_and_decimals_follow_the_range(qtbot, minimum: float, maximum: float, step: float, decimals: int) -> None:
    panel = ControlsPanel([FloatControl("x", minimum, minimum, maximum)])
    qtbot.addWidget(panel)
    spin_box = panel.findChild(QDoubleSpinBox)
    assert spin_box is not None
    assert spin_box.singleStep() == pytest.approx(step)
    assert spin_box.decimals() == decimals


def test_each_editor_drives_only_its_own_value(qtbot) -> None:
    """Every editor of a multi-control panel updates its own control, whatever the order they were built in."""
    panel = ControlsPanel(
        [
            TextControl("text", "a"),
            BoolControl("flag", default=False),
            ChoiceControl("choice", "x", ["x", "y"]),
            IntControl("count", 1, 0, 9),
            FloatControl("ratio", 0.5, 0.0, 1.0),
        ]
    )
    qtbot.addWidget(panel)
    _editor(panel, QLineEdit).setText("b")
    _editor(panel, QCheckBox).setChecked(True)
    _editor(panel, QComboBox).setCurrentIndex(1)
    _editor(panel, QSpinBox).setValue(7)
    _editor(panel, QDoubleSpinBox).setValue(0.75)

    assert panel.values() == {"text": "b", "flag": True, "choice": "y", "count": 7, "ratio": 0.75}


def test_labels_are_derived_from_names_and_are_buddies_and_accessible_names(qtbot) -> None:
    panel = ControlsPanel([TextControl("tile_type", "x"), IntControl("max_count", 1, 0, 5)])
    qtbot.addWidget(panel)
    labels = {label.text(): label for label in panel.findChildren(QLabel)}
    assert set(labels) == {"Tile Type", "Max Count"}
    assert isinstance(labels["Tile Type"].buddy(), QLineEdit)
    assert isinstance(labels["Max Count"].buddy(), QSpinBox)
    assert labels["Tile Type"].buddy().accessibleName() == "Tile Type"
    assert labels["Max Count"].buddy().accessibleName() == "Max Count"


def test_every_editor_is_owned_by_the_panel(qtbot) -> None:
    panel = ControlsPanel([TextControl("a", ""), BoolControl("b", default=True), ChoiceControl("c", "x", ["x"]), IntControl("d", 1, 0, 2)])
    qtbot.addWidget(panel)
    for editor_type in (QLineEdit, QCheckBox, QComboBox, QSpinBox):
        editor = panel.findChild(editor_type)
        assert editor is not None
        assert editor.parent() is panel


def test_no_controls_shows_empty_state_label(qtbot) -> None:
    panel = ControlsPanel([])
    qtbot.addWidget(panel)
    label = panel.findChild(QLabel, "controlsEmptyState")
    assert label is not None
    assert label.text() == NO_CONTROLS_MESSAGE
    assert NO_CONTROLS_MESSAGE == "No configurable properties for this component."
    assert panel.values() == {}


def test_empty_state_is_italic_and_styled_from_the_palette(qtbot) -> None:
    panel = ControlsPanel([])
    qtbot.addWidget(panel)
    label = panel.findChild(QLabel, "controlsEmptyState")
    assert label is not None
    assert label.font().italic()
    assert label.foregroundRole() == QPalette.ColorRole.PlaceholderText
    assert label.styleSheet() == ""
    assert panel.styleSheet() == ""


def test_panel_has_no_empty_state_when_there_are_controls(qtbot) -> None:
    panel = ControlsPanel([TextControl("a", "")])
    qtbot.addWidget(panel)
    assert panel.findChild(QLabel, "controlsEmptyState") is None


def test_int_editor_handles_the_full_supported_range(qtbot) -> None:
    panel = ControlsPanel([IntControl("n", 0, -(2**31), 2**31 - 1)])
    qtbot.addWidget(panel)
    spin_box = panel.findChild(QSpinBox)
    assert spin_box is not None
    assert (spin_box.minimum(), spin_box.maximum()) == (-(2**31), 2**31 - 1)


@pytest.mark.parametrize(
    ("default", "minimum", "maximum"),
    [(0.1234, 0.001, 1.001), (0.5, 0.0, 1.0), (12.75, -0.125, 100.0), (1e-6, 0.0, 0.001)],
)
def test_float_editor_shows_the_exact_default_and_range(qtbot, default: float, minimum: float, maximum: float) -> None:
    panel = ControlsPanel([FloatControl("x", default, minimum, maximum)])
    qtbot.addWidget(panel)
    spin_box = panel.findChild(QDoubleSpinBox)
    assert spin_box is not None
    assert spin_box.value() == panel.values()["x"] == default
    assert (spin_box.minimum(), spin_box.maximum()) == (minimum, maximum)


def test_float_editor_cannot_go_below_the_declared_minimum(qtbot) -> None:
    panel = ControlsPanel([FloatControl("x", 0.1234, 0.001, 1.001)])
    qtbot.addWidget(panel)
    spin_box = panel.findChild(QDoubleSpinBox)
    assert spin_box is not None
    spin_box.setValue(0.0)
    assert spin_box.value() == 0.001
    assert panel.values()["x"] == 0.001
