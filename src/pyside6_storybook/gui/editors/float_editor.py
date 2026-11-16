"""The editor of a ``FloatControl``: a spin box, with an optional slider beside it."""

from __future__ import annotations

import math

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSlider, QWidget

from pyside6_storybook.controls import FloatControl
from pyside6_storybook.gui.editors._wheel import guard_wheel
from pyside6_storybook.gui.editors.control_editor import ControlEditor


class FloatEditor(ControlEditor):
    """Edits a float in a spin box and, when the control asks for it, a slider; the two mirror each other.

    The slider has positions ``0..control.slider_steps``; position ``i`` means ``min(minimum + i * step, maximum)``. Moving the
    slider sets the spin box to that position's value; editing the spin box moves the slider to the nearest position and keeps the
    spin box's exact value. Emits once per user edit that changes the value.
    """

    def __init__(self, control: FloatControl, value: float, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting value.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._control = control
        self._value = value
        self._spin_box = QDoubleSpinBox(self)
        self._spin_box.setDecimals(control.effective_decimals)
        self._spin_box.setRange(control.minimum, control.maximum)
        self._spin_box.setSingleStep(control.effective_step)
        self._spin_box.setValue(value)
        guard_wheel(self._spin_box)
        self._spin_box.valueChanged.connect(self._on_spin_box_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._spin_box)
        self._slider: QSlider | None = None
        if control.slider:
            slider = QSlider(Qt.Orientation.Horizontal, self)
            slider.setRange(0, control.slider_steps)
            slider.setValue(self._position_of(value))
            guard_wheel(slider)
            slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(slider, stretch=1)
            self._slider = slider
        self.setFocusProxy(self._spin_box)

    def value(self) -> float:
        """Return the current value."""
        return self._spin_box.value()

    def set_accessible_texts(self, label: str, description: str) -> None:
        """Name the spin box with the label and the slider with the label followed by "slider"."""
        super().set_accessible_texts(label, description)
        if self._slider is not None:
            self._slider.setAccessibleName(f"{label} slider")
            self._slider.setAccessibleDescription(description)

    def _position_of(self, value: float) -> int:
        """Return the slider position whose value is nearest to ``value``.

        The two positions around ``value`` are compared by their actual values, because the last interval can be shorter than a
        step: in ``0..1`` with a step of ``0.3``, ``1.0`` is the last position (``1.0``), not the one before it (``0.9``).
        """
        steps = self._control.slider_steps
        exact = (value - self._control.minimum) / self._control.effective_step
        candidates = {max(0, min(position, steps)) for position in (math.floor(exact), math.ceil(exact))}
        return min(sorted(candidates), key=lambda position: abs(self._value_at(position) - value))

    def _value_at(self, position: int) -> float:
        """Return the value of a slider position; the last position is always exactly the maximum."""
        if position >= self._control.slider_steps:
            return self._control.maximum
        return min(self._control.minimum + position * self._control.effective_step, self._control.maximum)

    def _on_spin_box_changed(self, value: float) -> None:
        if self._slider is not None:
            with QSignalBlocker(self._slider):
                self._slider.setValue(self._position_of(value))
        self._emit_if_changed(value)

    def _on_slider_changed(self, position: int) -> None:
        with QSignalBlocker(self._spin_box):
            self._spin_box.setValue(self._value_at(position))
        self._emit_if_changed(self._spin_box.value())

    def _emit_if_changed(self, value: float) -> None:
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)


__all__ = ["FloatEditor"]
