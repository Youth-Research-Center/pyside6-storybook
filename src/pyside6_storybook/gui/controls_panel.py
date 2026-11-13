"""The controls panel: one labelled editor per control, built from stock Qt widgets."""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.controls import (
    BoolControl,
    ChoiceControl,
    Control,
    FloatControl,
    IntControl,
    TextControl,
)

NO_CONTROLS_MESSAGE = "No configurable properties for this component."

_FLOAT_STEPS_PER_RANGE = 100
_MIN_FLOAT_DECIMALS = 2
_MAX_FLOAT_DECIMALS = 10


class ControlsPanel(QWidget):
    """Renders one labelled editor per control and reports the live values.

    When there are no controls, a short empty-state label is shown instead of an empty form.

    Signals:
        valuesChanged: Emitted once per edit with a copy of the current values by control name.
    """

    valuesChanged = Signal(dict)

    def __init__(self, controls: Sequence[Control], parent: QWidget | None = None) -> None:
        """Create the panel.

        Args:
            controls: The controls to render.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._values: dict[str, object] = {control.name: control.default for control in controls}
        if not controls:
            self._build_empty_state()
            return
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        for control in controls:
            label_text = control.name.replace("_", " ").title()
            editor = self._build_editor(control)
            editor.setAccessibleName(label_text)
            label = QLabel(label_text, self)
            label.setBuddy(editor)
            form.addRow(label, editor)

    def values(self) -> dict[str, object]:
        """Return a copy of the current value of every control, keyed by control name."""
        return dict(self._values)

    def _build_empty_state(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(NO_CONTROLS_MESSAGE, self)
        label.setObjectName("controlsEmptyState")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        font = label.font()
        font.setItalic(True)
        label.setFont(font)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(label)

    def _build_editor(self, control: Control) -> QWidget:
        if isinstance(control, TextControl):
            line_edit = QLineEdit(control.default, self)
            line_edit.textChanged.connect(partial(self._set_value, control.name))
            return line_edit
        if isinstance(control, BoolControl):
            check_box = QCheckBox(self)
            check_box.setChecked(control.default)
            check_box.toggled.connect(partial(self._set_value, control.name))
            return check_box
        if isinstance(control, ChoiceControl):
            combo = QComboBox(self)
            combo.addItems(control.options)
            combo.setCurrentIndex(control.options.index(control.default))
            combo.currentIndexChanged.connect(partial(self._set_choice, control))
            return combo
        if isinstance(control, IntControl):
            spin_box = QSpinBox(self)
            spin_box.setRange(control.minimum, control.maximum)
            spin_box.setValue(control.default)
            spin_box.valueChanged.connect(partial(self._set_value, control.name))
            return spin_box
        if isinstance(control, FloatControl):
            double_spin_box = QDoubleSpinBox(self)
            step, decimals = _float_step_and_decimals(control)
            double_spin_box.setDecimals(decimals)
            double_spin_box.setRange(control.minimum, control.maximum)
            double_spin_box.setSingleStep(step)
            double_spin_box.setValue(control.default)
            double_spin_box.valueChanged.connect(partial(self._set_value, control.name))
            return double_spin_box
        raise TypeError(f"Unsupported control type: {type(control)!r}")

    def _set_value(self, name: str, value: object) -> None:
        self._values[name] = value
        self.valuesChanged.emit(self.values())

    def _set_choice(self, control: ChoiceControl, index: int) -> None:
        if index >= 0:
            self._set_value(control.name, control.options[index])


def _float_step_and_decimals(control: FloatControl) -> tuple[float, int]:
    """Derive a spin box step (a power of ten near 1% of the range) and the decimals the editor shows.

    The decimals cover the step, the default and both bounds, so the editor shows the exact default and cannot round a bound
    (``QDoubleSpinBox`` rounds its range and value to its decimals). Values that need more than ``_MAX_FLOAT_DECIMALS`` decimals
    are shown rounded.
    """
    span = control.maximum - control.minimum
    if span <= 0:
        step, step_decimals = 1.0, _MIN_FLOAT_DECIMALS
    else:
        exponent = round(math.log10(span / _FLOAT_STEPS_PER_RANGE))
        step, step_decimals = 10.0**exponent, -exponent
    value_decimals = max(_decimals_needed(value) for value in (control.default, control.minimum, control.maximum))
    return step, max(_MIN_FLOAT_DECIMALS, step_decimals, value_decimals)


def _decimals_needed(value: float) -> int:
    """Return the fewest decimals (up to ``_MAX_FLOAT_DECIMALS``) that represent ``value`` without changing it."""
    for decimals in range(_MAX_FLOAT_DECIMALS + 1):
        if math.isclose(round(value, decimals), value, rel_tol=1e-12, abs_tol=1e-15):
            return decimals
    return _MAX_FLOAT_DECIMALS


__all__ = ["NO_CONTROLS_MESSAGE", "ControlsPanel"]
