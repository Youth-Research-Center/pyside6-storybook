"""The editor of an ``IntControl``: a spin box, with an optional slider beside it."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QHBoxLayout, QSlider, QSpinBox, QWidget

from pyside6_storybook.controls import IntControl
from pyside6_storybook.gui.editors._wheel import guard_wheel
from pyside6_storybook.gui.editors.control_editor import ControlEditor


class IntEditor(ControlEditor):
    """Edits an int in a spin box and, when the control asks for it, a slider; the two mirror each other.

    Emits once per user edit that changes the value.
    """

    def __init__(self, control: IntControl, value: int, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting value.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._value = value
        self._spin_box = QSpinBox(self)
        self._spin_box.setRange(control.minimum, control.maximum)
        self._spin_box.setSingleStep(control.step)
        self._spin_box.setValue(value)
        guard_wheel(self._spin_box)
        self._spin_box.valueChanged.connect(self._on_spin_box_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._spin_box)
        self._slider: QSlider | None = None
        if control.slider:
            slider = QSlider(Qt.Orientation.Horizontal, self)
            slider.setRange(control.minimum, control.maximum)
            slider.setSingleStep(control.step)
            slider.setValue(value)
            guard_wheel(slider)
            slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(slider, stretch=1)
            self._slider = slider
        self.setFocusProxy(self._spin_box)

    def value(self) -> int:
        """Return the current value."""
        return self._spin_box.value()

    def set_accessible_texts(self, label: str, description: str) -> None:
        """Name the spin box with the label and the slider with the label followed by "slider"."""
        super().set_accessible_texts(label, description)
        if self._slider is not None:
            self._slider.setAccessibleName(f"{label} slider")
            self._slider.setAccessibleDescription(description)

    def _on_spin_box_changed(self, value: int) -> None:
        if self._slider is not None:
            with QSignalBlocker(self._slider):
                self._slider.setValue(value)
        self._emit_if_changed(value)

    def _on_slider_changed(self, value: int) -> None:
        with QSignalBlocker(self._spin_box):
            self._spin_box.setValue(value)
        self._emit_if_changed(value)

    def _emit_if_changed(self, value: int) -> None:
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)


__all__ = ["IntEditor"]
